"""Tests PressReleaseDrafter."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import yaml

from argos_ops.agents.press_release_drafter import (
    DraftStats,
    ReleaseRequest,
    build_release_embed,
    draft_release,
    load_queue,
)
from argos_ops.notifications.discord import GREEN, YELLOW


def test_load_queue_skips_missing_required(tmp_path: Path) -> None:
    path = tmp_path / "q.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                "releases": [
                    {"slug": "a", "title": "T"},
                    {"title": "no-slug"},
                ]
            }
        ),
        encoding="utf-8",
    )
    assert len(load_queue(path)) == 1


def test_draft_release_contains_canonical_sections() -> None:
    req = ReleaseRequest(
        slug="launch",
        title="Argos lance X",
        angle="product",
        summary="Sommaire",
        body="Corps du communiqué",
        founder_quote="Une citation",
    )
    md = draft_release(req, now=datetime(2026, 6, 1, tzinfo=UTC))
    assert "# Argos lance X" in md
    assert "## Contexte" in md
    assert "## Citation" in md
    assert "## À propos d'Omnividens" in md
    assert "## Contacts presse" in md
    assert "omnividens.fr" in md
    assert "Une citation" in md
    assert "Argos — on scanne, vous corrigez" in md


def test_draft_release_handles_missing_quote() -> None:
    req = ReleaseRequest(slug="x", title="X", angle="finance", summary="s", body="")
    md = draft_release(req)
    assert "citation founder à compléter" in md
    assert "à compléter" in md  # le body fallback


def test_build_release_embed_color() -> None:
    drafted = DraftStats(queued=2, drafted=1)
    assert build_release_embed(drafted).color == GREEN
    none = DraftStats(queued=2, drafted=0, skipped_existing=2)
    assert build_release_embed(none).color == YELLOW
