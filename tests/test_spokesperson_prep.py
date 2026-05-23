"""Tests SpokespersonPrep."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import yaml

from argos_ops.agents.spokesperson_prep import (
    QUESTION_BANK,
    Interview,
    PrepStats,
    build_prep_embed,
    draft_qa_brief,
    load_upcoming,
)
from argos_ops.notifications.discord import GREEN, YELLOW


def test_load_upcoming_parses_dates(tmp_path: Path) -> None:
    path = tmp_path / "i.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                "interviews": [
                    {
                        "slug": "zdnet",
                        "outlet": "ZDNet",
                        "journalist": "Marie",
                        "date": "2026-06-10",
                        "beat": "cyber",
                    },
                    {"slug": "bad", "date": "not-date"},
                ]
            }
        ),
        encoding="utf-8",
    )
    out = load_upcoming(path)
    assert len(out) == 1
    assert out[0].date == date(2026, 6, 10)


def test_draft_qa_brief_includes_questions_for_beat() -> None:
    interview = Interview(
        slug="x",
        outlet="ZDNet",
        journalist="J",
        date=date(2026, 6, 15),
        beat="cyber",
    )
    md = draft_qa_brief(interview, founder_stats={"MRR": "5k€"})
    assert "ZDNet" in md
    assert "no-go topics" in md.lower()
    # Au moins une question canonique cyber
    assert any(q in md for q in QUESTION_BANK["cyber"])
    assert "5k€" in md


def test_draft_qa_brief_uses_default_beat_when_unknown() -> None:
    interview = Interview(
        slug="x",
        outlet="X",
        journalist="J",
        date=date(2026, 6, 15),
        beat="space-pirates",
    )
    md = draft_qa_brief(interview, founder_stats={})
    # Doit utiliser cyber par défaut
    assert any(q in md for q in QUESTION_BANK["cyber"])


def test_build_prep_embed_color() -> None:
    briefed = PrepStats(upcoming=2, briefed=2)
    assert build_prep_embed(briefed).color == GREEN
    queued = PrepStats(upcoming=2, briefed=0, skipped_existing=2)
    assert build_prep_embed(queued).color == YELLOW
