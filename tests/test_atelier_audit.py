"""Tests du journal d'audit atelier (Axe 4) — écriture redactée + best-effort."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from argos_ops.ops_dashboard import atelier_audit


def test_excerpt_truncates_and_strips() -> None:
    assert atelier_audit.excerpt(None) is None
    assert atelier_audit.excerpt("") is None
    assert atelier_audit.excerpt("  hello  ") == "hello"
    long = "x" * 400
    out = atelier_audit.excerpt(long)
    assert out is not None
    assert out.endswith("…")
    assert len(out) <= atelier_audit._EXCERPT_MAX + 1


def test_record_writes_redacted_jsonl(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(atelier_audit, "AUDIT_DIR", tmp_path / "audit")
    atelier_audit.record(
        atelier_audit.AuditEvent(
            action="console_act",
            mode="console",
            bot="AdBot",
            prompt_excerpt="colle ce token sk-ABCDEFGHIJKLMNOPQRSTUVWX stp",
            verdict="auto_send",
            approved=True,
            acted=True,
            live=True,
            outcome="executed",
        )
    )
    files = list((tmp_path / "audit").glob("atelier-*.jsonl"))
    assert len(files) == 1
    line = files[0].read_text(encoding="utf-8").strip()
    data = json.loads(line)
    assert data["action"] == "console_act"
    assert data["bot"] == "AdBot"
    assert data["acted"] is True
    assert data["live"] is True
    assert data["outcome"] == "executed"
    assert "ts" in data
    # Le secret collé dans le prompt est redacté AVANT écriture sur disque.
    assert "sk-ABCDEFGHIJKLMNOPQRSTUVWX" not in line
    assert "[REDACTED]" in line


def test_record_appends_same_day(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(atelier_audit, "AUDIT_DIR", tmp_path / "audit")
    atelier_audit.record(atelier_audit.AuditEvent(action="atelier_turn", mode="read"))
    atelier_audit.record(atelier_audit.AuditEvent(action="mcp_run_bot", mode="fleet", bot="EmailBot"))
    files = list((tmp_path / "audit").glob("atelier-*.jsonl"))
    assert len(files) == 1  # même fichier journalier
    lines = files[0].read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2


def test_record_is_best_effort_and_never_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # AUDIT_DIR dont le parent est un FICHIER → mkdir échoue → record avale l'erreur.
    blocker = tmp_path / "blocker"
    blocker.write_text("x", encoding="utf-8")
    monkeypatch.setattr(atelier_audit, "AUDIT_DIR", blocker / "sub")
    # Ne doit pas lever (l'action prime sur sa trace).
    atelier_audit.record(atelier_audit.AuditEvent(action="console_act", bot="AdBot"))
