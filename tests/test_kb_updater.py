"""Tests unitaires de ``argos_ops.agents.kb_updater`` (P22.G)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from argos_ops.agents.kb_updater import (
    KBUpdaterStats,
    _draft_kb_article,
    build_kb_embed,
    detect_gaps,
)
from argos_ops.cs.models import CustomerPlan, SupportTicket


def _ticket(ticket_id: str, subject: str) -> SupportTicket:
    return SupportTicket(
        ticket_id=ticket_id,
        customer_id="acme-sa",
        subject=subject,
        body="...",
        opened_at=date(2026, 5, 20),
        plan=CustomerPlan.STARTER,
    )


def test_detect_gaps_clusters_repeated_keywords() -> None:
    tickets = [
        _ticket("t1", "Scan GraphQL bloque sur authentification"),
        _ticket("t2", "Authentification SSO ne fonctionne pas"),
        _ticket("t3", "Problème authentification API"),
    ]
    gaps = detect_gaps(tickets)
    themes = [g.theme for g in gaps]
    assert "authentification" in themes


def test_detect_gaps_ignores_single_occurrence() -> None:
    tickets = [_ticket("t1", "Question random sujet unique")]
    gaps = detect_gaps(tickets, min_occurrences=2)
    assert gaps == []


def test_draft_kb_article_writes_skeleton(tmp_path: Path) -> None:
    from argos_ops.agents.kb_updater import KBGap

    gap = KBGap(theme="authentification", occurrences=3, sample_tickets=["t1", "t2", "t3"])
    path = _draft_kb_article(gap, tmp_path)
    assert path.exists()
    content = path.read_text(encoding="utf-8")
    assert "Symptôme" in content
    assert "authentification" in content.lower()
    assert "kb-rag" in content
    assert "claude-judge" in content


def test_build_kb_embed_color_yellow_when_drafts() -> None:
    stats = KBUpdaterStats(tickets_scanned=10, themes_detected=2, drafts_created=2)
    assert build_kb_embed(stats).color == 0xF1C40F


def test_build_kb_embed_color_green_when_no_drafts() -> None:
    stats = KBUpdaterStats(tickets_scanned=5, themes_detected=0, drafts_created=0)
    assert build_kb_embed(stats).color == 0x2ECC71
