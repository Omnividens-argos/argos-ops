"""Tests unitaires ContentBot (P9 full).

Couvre :
- find_ready_drafts() : filtre status=validated + scheduled_for <= now
- publish_draft() : dispatch LinkedIn / Mastodon + déplacement vers published/
- build_content_embed() : couleur vert/jaune selon failures
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest

from argos_ops.agents.content_bot import ContentRunStats, build_content_embed
from argos_ops.notifications.discord import GREEN, YELLOW
from argos_ops.social.linkedin import LinkedInClient
from argos_ops.social.publisher import find_ready_drafts, publish_draft


def _make_draft(
    tmp_path: Path,
    *,
    slug: str,
    status: str,
    channel: str,
    scheduled_for: datetime,
    body: str = "Hello cyber world",
) -> Path:
    drafts = tmp_path / "drafts"
    drafts.mkdir(parents=True, exist_ok=True)
    path = drafts / f"{slug}.md"
    fm = (
        f"---\nstatus: {status}\nchannel: {channel}\n"
        f"scheduled_for: {scheduled_for.isoformat()}\n---\n{body}\n"
    )
    path.write_text(fm, encoding="utf-8")
    return path


def test_build_content_embed_green_without_failures() -> None:
    stats = ContentRunStats(ready=2, published_live=0, published_shadow=2)
    embed = build_content_embed(stats, live_mode=False)
    assert embed.color == GREEN


def test_build_content_embed_yellow_when_failures() -> None:
    stats = ContentRunStats(ready=2, published_shadow=1, failures=1)
    embed = build_content_embed(stats, live_mode=True)
    assert embed.color == YELLOW


def test_find_ready_drafts_filters_by_status_and_schedule(tmp_path: Path) -> None:
    now = datetime.now(UTC)
    drafts_dir = tmp_path / "drafts"
    drafts_dir.mkdir()

    ready = drafts_dir / "ready.md"
    ready.write_text(
        f"---\nstatus: validated\nchannel: linkedin\n"
        f"scheduled_for: {(now - timedelta(minutes=5)).isoformat()}\n---\nbody\n",
        encoding="utf-8",
    )
    not_yet = drafts_dir / "future.md"
    not_yet.write_text(
        f"---\nstatus: validated\nchannel: linkedin\n"
        f"scheduled_for: {(now + timedelta(hours=2)).isoformat()}\n---\nbody\n",
        encoding="utf-8",
    )
    pending = drafts_dir / "pending.md"
    pending.write_text(
        f"---\nstatus: pending\nchannel: linkedin\n"
        f"scheduled_for: {(now - timedelta(minutes=5)).isoformat()}\n---\nbody\n",
        encoding="utf-8",
    )

    with patch("argos_ops.social.publisher.DRAFTS_DIR", drafts_dir):
        out = find_ready_drafts(now=now)

    assert [p.name for p in out] == ["ready.md"]


@pytest.mark.asyncio
async def test_publish_draft_shadow_mode_moves_to_published(tmp_path: Path) -> None:
    now = datetime.now(UTC)
    draft = _make_draft(
        tmp_path,
        slug="test-post",
        status="validated",
        channel="linkedin",
        scheduled_for=now - timedelta(minutes=1),
    )
    published_dir = tmp_path / "published"

    with patch("argos_ops.social.publisher.PUBLISHED_DIR", published_dir):
        linkedin = LinkedInClient()
        result = await publish_draft(draft, linkedin=linkedin)

    assert result.status == "shadow"
    assert result.platform == "linkedin"
    assert not draft.exists()
    moved = published_dir / "test-post.md"
    assert moved.exists()
    content = moved.read_text(encoding="utf-8")
    assert "status: published_shadow" in content
    assert "published_at:" in content


@pytest.mark.asyncio
async def test_publish_draft_unknown_channel_fails(tmp_path: Path) -> None:
    draft = _make_draft(
        tmp_path,
        slug="bad-channel",
        status="validated",
        channel="reddit",  # retiré par D-022
        scheduled_for=datetime.now(UTC) - timedelta(minutes=1),
    )
    result = await publish_draft(draft)
    assert result.status == "failed"
    assert "channel inconnu" in (result.error or "")
