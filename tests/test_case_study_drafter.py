"""Tests CaseStudyDrafter."""

from __future__ import annotations

from pathlib import Path

import yaml

from argos_ops.agents.case_study_drafter import (
    CaseStudyCandidate,
    DrafterStats,
    build_drafter_embed,
    draft_case_study,
    load_candidates,
)
from argos_ops.notifications.discord import GREEN, YELLOW


def test_load_candidates_skips_missing_required(tmp_path: Path) -> None:
    path = tmp_path / "c.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                "candidates": [
                    {"slug": "ok", "customer": "Acme"},
                    {"customer": "no-slug"},
                ]
            }
        ),
        encoding="utf-8",
    )
    out = load_candidates(path)
    assert len(out) == 1
    assert out[0].slug == "ok"


def test_draft_case_study_includes_canonical_sections() -> None:
    c = CaseStudyCandidate(
        slug="acme",
        customer="Acme",
        sector="Industrie",
        context="80 personnes",
        problem="conformité",
        solution="scan Argos",
        results=["12 findings"],
        quote="Top",
    )
    md = draft_case_study(c)
    assert "## Contexte" in md
    assert "## Problème" in md
    assert "## Solution Argos" in md
    assert "## Résultats" in md
    assert "## Verbatim" in md
    assert "12 findings" in md
    assert "« Top »" in md


def test_draft_case_study_handles_missing_quote_and_results() -> None:
    c = CaseStudyCandidate(slug="b", customer="B", sector="", context="", problem="", solution="")
    md = draft_case_study(c)
    assert "(à compléter)" in md
    assert "À solliciter via TestimonialHunter" in md


def test_build_drafter_embed_color() -> None:
    drafted = DrafterStats(candidates=2, drafted=1)
    assert build_drafter_embed(drafted).color == GREEN
    none_yet = DrafterStats(candidates=2, drafted=0, skipped_existing=2)
    assert build_drafter_embed(none_yet).color == YELLOW
