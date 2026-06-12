"""Tests du cerveau LLM partagé (``argos_ops.brain``, Axe 2).

Aucun subprocess réel : le runner bloquant est monkeypatché. On couvre
le contrat central — le cerveau ne raise jamais, ``ok=False`` ⇒ fallback.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from argos_ops import brain
from argos_ops.brain import (
    BrainAnswer,
    build_brain_argv,
    extract_json_object,
    parse_cli_payload,
    think_json,
)


def _settings(enabled: bool) -> SimpleNamespace:
    return SimpleNamespace(ops_brain_enabled=enabled, ops_atelier_claude_bin="claude")


# =============================================================================
# Briques pures
# =============================================================================
def test_build_brain_argv_one_shot_plan_mode() -> None:
    argv = build_brain_argv("classifie ça", claude_bin="C:/bin/claude.exe")
    assert argv[0] == "C:/bin/claude.exe"
    assert argv[1:3] == ["-p", "classifie ça"]
    assert "--output-format" in argv and "json" in argv
    assert "--permission-mode" in argv and "plan" in argv


def test_parse_cli_payload_extracts_result() -> None:
    stdout = json.dumps({"type": "result", "result": '{"ok": true}', "cost": 0.0})
    assert parse_cli_payload(stdout) == '{"ok": true}'


def test_parse_cli_payload_rejects_garbage() -> None:
    with pytest.raises(ValueError):
        parse_cli_payload("pas du json")
    with pytest.raises(ValueError):
        parse_cli_payload(json.dumps({"type": "result"}))  # pas de champ result


def test_extract_json_object_raw_fenced_and_noisy() -> None:
    assert extract_json_object('{"a": 1}') == {"a": 1}
    assert extract_json_object('```json\n{"a": 1}\n```') == {"a": 1}
    assert extract_json_object('Voilà :\n{"a": 1}\nmerci') == {"a": 1}


def test_extract_json_object_rejects_non_object() -> None:
    with pytest.raises(ValueError):
        extract_json_object("aucun json ici")
    with pytest.raises(ValueError):
        extract_json_object("[1, 2, 3]")
    with pytest.raises(ValueError):
        extract_json_object("   ")


# =============================================================================
# think_json — contrat « ne raise jamais »
# =============================================================================
@pytest.mark.asyncio
async def test_think_json_disabled_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(brain, "get_settings", lambda: _settings(False))
    answer = await think_json("question")
    assert answer == BrainAnswer(
        ok=False, data=None, raw=None, engine="disabled", error="OPS_BRAIN_ENABLED=false"
    )


@pytest.mark.asyncio
async def test_think_json_happy_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(brain, "get_settings", lambda: _settings(True))
    model_text = 'Réponse :\n```json\n{"priority": "P0"}\n```'
    cli_stdout = json.dumps({"type": "result", "result": model_text})
    captured: dict[str, object] = {}

    def fake_run(argv: list[str], timeout_s: int) -> str:
        captured["argv"] = argv
        captured["timeout_s"] = timeout_s
        return cli_stdout

    monkeypatch.setattr(brain, "_run_claude_blocking", fake_run)
    answer = await think_json("classifie", timeout_s=42)
    assert answer.ok is True
    assert answer.engine == "claude"
    assert answer.data == {"priority": "P0"}
    assert answer.raw == model_text
    assert captured["timeout_s"] == 42
    assert isinstance(captured["argv"], list) and captured["argv"][1] == "-p"


@pytest.mark.asyncio
async def test_think_json_engine_failure_returns_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(brain, "get_settings", lambda: _settings(True))

    def boom(argv: list[str], timeout_s: int) -> str:
        raise RuntimeError("claude exit 1 : binaire absent")

    monkeypatch.setattr(brain, "_run_claude_blocking", boom)
    answer = await think_json("classifie")
    assert answer.ok is False
    assert answer.engine == "error"
    assert "binaire absent" in (answer.error or "")


@pytest.mark.asyncio
async def test_think_json_truncates_huge_prompt(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(brain, "get_settings", lambda: _settings(True))
    seen: dict[str, int] = {}

    def fake_run(argv: list[str], timeout_s: int) -> str:
        seen["prompt_len"] = len(argv[2])
        return json.dumps({"result": '{"ok": 1}'})

    monkeypatch.setattr(brain, "_run_claude_blocking", fake_run)
    await think_json("x" * (brain.MAX_PROMPT_CHARS + 5_000))
    assert seen["prompt_len"] == brain.MAX_PROMPT_CHARS
