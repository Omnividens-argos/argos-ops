"""Tests BacklinkOutreach."""

from __future__ import annotations

from pathlib import Path

import yaml

from argos_ops.agents.backlink_outreach import (
    BacklinkTarget,
    OutreachStats,
    build_outreach_embed,
    draft_email,
    load_targets,
)
from argos_ops.notifications.discord import GREEN, YELLOW


def test_load_targets_filters_invalid(tmp_path: Path) -> None:
    path = tmp_path / "t.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                "targets": [
                    {
                        "slug": "ok",
                        "site_url": "https://example.com",
                        "contact_email": "a@example.com",
                        "angle": "ressource",
                        "status": "queued",
                    },
                    {"slug": "bad", "site_url": "x", "contact_email": "no-at-sign"},
                    "not-a-dict",
                ]
            }
        ),
        encoding="utf-8",
    )
    targets = load_targets(path)
    assert len(targets) == 1
    assert targets[0].slug == "ok"


def test_draft_email_contains_frontmatter_and_tagline() -> None:
    target = BacklinkTarget(
        slug="korben",
        site_url="https://korben.info",
        contact_email="hello@korben.info",
        angle="guest post",
    )
    body = draft_email(target)
    assert "status: drafted" in body
    assert "korben" in body
    assert "Argos — on scanne, vous corrigez" in body
    assert "Email rédigé par notre assistant Argos Ops" in body


def test_build_outreach_embed_color() -> None:
    ok = OutreachStats(targets_read=5, drafted=3)
    assert build_outreach_embed(ok).color == GREEN
    bad = OutreachStats(targets_read=5, drafted=3, skipped_invalid=1)
    assert build_outreach_embed(bad).color == YELLOW
