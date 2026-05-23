"""Tests WebinarPromoter."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from unittest.mock import patch

import yaml

from argos_ops.agents.webinar_promoter import (
    Webinar,
    draft_assets,
    load_upcoming,
)


def test_load_upcoming_parses_dates(tmp_path: Path) -> None:
    path = tmp_path / "w.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                "webinars": [
                    {
                        "slug": "test-1",
                        "title": "Webinar test",
                        "date": "2026-06-15",
                        "register_url": "https://omnividens.fr/w/test-1",
                    },
                    {"slug": "bad", "title": "no date"},
                ]
            }
        ),
        encoding="utf-8",
    )
    out = load_upcoming(path)
    assert len(out) == 1
    assert out[0].slug == "test-1"
    assert out[0].date == date(2026, 6, 15)


def test_draft_assets_creates_3_posts_and_2_md(tmp_path: Path) -> None:
    drafts = tmp_path / "drafts"
    webinars = tmp_path / "webinars"
    today = date(2026, 6, 1)
    webinar = Webinar(
        slug="june-test",
        title="June Test",
        date=date(2026, 6, 15),
        register_url="https://omnividens.fr/w/june",
        description="Test",
    )
    with (
        patch("argos_ops.agents.webinar_promoter.DRAFTS_DIR", drafts),
        patch("argos_ops.agents.webinar_promoter.WEBINARS_DIR", webinars),
    ):
        created = draft_assets(webinar, today=today)
    assert any("webinar-june-test-j14" in str(p) for p in created)
    assert any("webinar-june-test-j7" in str(p) for p in created)
    assert any("webinar-june-test-j1" in str(p) for p in created)
    assert (webinars / "june-test" / "email_teaser.md").exists()
    assert (webinars / "june-test" / "replay_edit.md").exists()


def test_draft_assets_idempotent(tmp_path: Path) -> None:
    drafts = tmp_path / "drafts"
    webinars = tmp_path / "webinars"
    webinar = Webinar(
        slug="idem",
        title="Idem",
        date=date(2026, 6, 15),
        register_url="https://omnividens.fr/w/idem",
    )
    with (
        patch("argos_ops.agents.webinar_promoter.DRAFTS_DIR", drafts),
        patch("argos_ops.agents.webinar_promoter.WEBINARS_DIR", webinars),
    ):
        first = draft_assets(webinar, today=date(2026, 6, 1))
        second = draft_assets(webinar, today=date(2026, 6, 1))
    assert len(first) == 5
    assert len(second) == 0
