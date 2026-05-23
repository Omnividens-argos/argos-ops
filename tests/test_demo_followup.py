"""Tests unitaires de ``argos_ops.agents.demo_followup`` (P22.H)."""

from __future__ import annotations

from pathlib import Path

from argos_ops.agents.demo_followup import (
    FollowupStats,
    _draft_followup,
    _load_demos,
    _persist_demos,
    build_followup_embed,
)


def _entry() -> dict:
    return {
        "demo_id": "acme-2026-05-23",
        "first_name": "Marc",
        "contact_email": "marc@acme.fr",
        "when": "2026-05-23",
        "pain_points": ["audit RGPD passé en panique"],
        "next_steps": [["Argos", "envoyer devis"], ["Marc", "valider board"]],
        "attachments": ["devis.pdf"],
        "focus_topic": "intégration GitLab CI",
        "next_milestone": "vendredi",
        "status": "pending",
    }


def test_draft_followup_writes_md_with_frontmatter(tmp_path: Path) -> None:
    drafts_dir = tmp_path / "drafts"
    path = _draft_followup(_entry(), drafts_dir)
    content = path.read_text(encoding="utf-8")
    assert content.startswith("---\n")
    assert "demo_id: acme-2026-05-23" in content
    assert "**Argos** : envoyer devis" in content
    assert "audit RGPD passé en panique" in content


def test_load_demos_returns_empty_when_missing(tmp_path: Path) -> None:
    assert _load_demos(tmp_path / "absent.yaml") == []


def test_persist_and_load_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "done.yaml"
    _persist_demos(path, [_entry()])
    loaded = _load_demos(path)
    assert len(loaded) == 1
    assert loaded[0]["demo_id"] == "acme-2026-05-23"


def test_followup_embed_green_if_no_drafts() -> None:
    embed = build_followup_embed(FollowupStats(pending_seen=0, drafts_created=0))
    assert embed.color == 0x2ECC71


def test_followup_embed_yellow_if_drafts() -> None:
    embed = build_followup_embed(FollowupStats(pending_seen=1, drafts_created=1, drafts=["a"]))
    assert embed.color == 0xF1C40F
