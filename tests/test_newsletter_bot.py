"""Tests NewsletterBot."""

from __future__ import annotations

from pathlib import Path

from argos_ops.agents.newsletter_bot import (
    NewsletterDraft,
    build_newsletter_embed,
    build_newsletter_markdown,
)
from argos_ops.notifications.discord import GREEN, YELLOW


def test_build_newsletter_markdown_includes_posts_and_trends() -> None:
    md = build_newsletter_markdown(
        month="2026-05",
        blog_posts=[
            {"title": "Pentest supply chain", "url": "https://omnividens.fr/blog/sc"}
        ],
        trend_digests=["# Top trends\n1. CVE Ivanti"],
    )
    assert "2026-05" in md
    assert "Pentest supply chain" in md
    assert "CVE Ivanti" in md
    assert "status: draft" in md
    assert "Désabonnement" in md


def test_build_newsletter_markdown_handles_empty_inputs() -> None:
    md = build_newsletter_markdown(month="2026-05", blog_posts=[], trend_digests=[])
    assert "2026-05" in md
    assert "Articles récents" not in md
    assert "Actu cyber" not in md


def test_build_newsletter_embed_color(tmp_path: Path) -> None:
    fake = tmp_path / "2026-05.md"
    fake.write_text("x", encoding="utf-8")
    empty = NewsletterDraft(month="2026-05", path=fake, blog_count=0, trends_count=0)
    assert build_newsletter_embed(empty).color == YELLOW
    full = NewsletterDraft(month="2026-05", path=fake, blog_count=4, trends_count=2)
    assert build_newsletter_embed(full).color == GREEN
