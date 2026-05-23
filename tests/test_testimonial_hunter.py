"""Tests TestimonialHunter."""

from __future__ import annotations

from pathlib import Path

import yaml

from argos_ops.agents.testimonial_hunter import (
    HunterStats,
    NpsHit,
    build_hunter_embed,
    draft_request,
    load_nps,
)
from argos_ops.notifications.discord import GREEN, YELLOW


def test_load_nps_skips_missing_keys(tmp_path: Path) -> None:
    path = tmp_path / "nps.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                "responses": [
                    {
                        "slug": "a",
                        "score": 10,
                        "contact_name": "X",
                        "contact_email": "x@y.fr",
                        "company": "Y",
                    },
                    {"slug": "incomplete"},
                ]
            }
        ),
        encoding="utf-8",
    )
    assert len(load_nps(path)) == 1


def test_draft_request_includes_quote_when_comment_present() -> None:
    hit = NpsHit(
        slug="acme",
        contact_name="Alice",
        contact_email="alice@acme.fr",
        company="Acme",
        score=9,
        comment="Très efficace !",
    )
    body = draft_request(hit)
    assert "Très efficace" in body
    assert "Alice" in body
    assert "status: drafted" in body
    assert "9/10" in body


def test_draft_request_no_quote_when_no_comment() -> None:
    hit = NpsHit(
        slug="b",
        contact_name="Bob",
        contact_email="b@b.fr",
        company="B",
        score=10,
    )
    body = draft_request(hit)
    # Pas de bloc citation > au début du body (le « ok » reste dans la prose)
    assert "> «" not in body


def test_build_hunter_embed_color() -> None:
    drafted = HunterStats(total_hits=2, high_score_hits=1, drafted=1)
    assert build_hunter_embed(drafted).color == GREEN
    nothing = HunterStats(total_hits=0)
    assert build_hunter_embed(nothing).color == YELLOW
