"""Tests de l'historique des conversations de l'Atelier (Cockpit)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from argos_ops.ops_dashboard import atelier_history


def test_sessions_dir_encodes_path_safely() -> None:
    d = atelier_history.sessions_dir(Path("C:/Foo/Bar"))
    assert ".claude" in d.parts and "projects" in d.parts
    # Le nom encodé ne contient ni séparateur de chemin ni deux-points.
    assert ":" not in d.name
    assert "\\" not in d.name and "/" not in d.name


def test_content_text_handles_str_and_blocks() -> None:
    assert atelier_history._content_text("salut") == "salut"
    assert (
        atelier_history._content_text(
            [{"type": "text", "text": "a"}, {"type": "text", "text": "b"}]
        )
        == "a\nb"
    )
    assert atelier_history._content_text(None) == ""


def _write_session(tmp_path: Path, lines: list[dict]) -> str:
    (tmp_path / "sess-123.jsonl").write_text(
        "\n".join(json.dumps(line) for line in lines), encoding="utf-8"
    )
    return "sess-123"


def test_read_transcript_parses_roles(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(atelier_history, "sessions_dir", lambda *a, **k: tmp_path)
    sid = _write_session(
        tmp_path,
        [
            {"type": "queue-operation"},  # ignoré
            {
                "type": "user",
                "message": {"content": [{"type": "text", "text": "lance TrendSpotter"}]},
            },
            {
                "type": "assistant",
                "message": {
                    "content": [
                        {"type": "text", "text": "OK, je lance."},
                        {"type": "tool_use", "name": "run_bot", "id": "t1"},
                    ]
                },
            },
            {
                "type": "user",
                "message": {"content": [{"type": "tool_result", "content": "done"}]},
            },
        ],
    )
    items = atelier_history.read_transcript(sid, tmp_path)
    roles = [it["role"] for it in items]
    assert roles == ["user", "assistant", "tool", "tool_result"]
    assert items[0]["text"] == "lance TrendSpotter"
    assert items[2]["name"] == "run_bot"
    assert items[3]["text"] == "done"


def test_read_transcript_rejects_path_traversal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(atelier_history, "sessions_dir", lambda *a, **k: tmp_path)
    assert atelier_history.read_transcript("../secret", tmp_path) == []
    assert atelier_history.read_transcript("a/b", tmp_path) == []
