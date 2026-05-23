"""Tests ReplyBot."""

from __future__ import annotations

from pathlib import Path

import yaml

from argos_ops.agents.reply_bot import (
    Mention,
    ReplyStats,
    build_reply_embed,
    draft_reply,
    load_mentions,
)
from argos_ops.notifications.discord import GREEN, YELLOW


def test_load_mentions_skips_missing_id(tmp_path: Path) -> None:
    path = tmp_path / "m.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                "mentions": [
                    {"id": "1", "platform": "linkedin", "original_text": "hi"},
                    {"platform": "linkedin", "original_text": "no-id"},
                ]
            }
        ),
        encoding="utf-8",
    )
    out = load_mentions(path)
    assert len(out) == 1
    assert out[0].id == "1"


def test_draft_reply_tone_varies_by_sentiment() -> None:
    pos = draft_reply(
        Mention(id="1", platform="linkedin", author="Alice", mention_url="", original_text="t",
                sentiment="positive")
    )
    assert "Merci Alice" in pos

    neg = draft_reply(
        Mention(id="2", platform="linkedin", author="Bob", mention_url="", original_text="t",
                sentiment="negative")
    )
    assert "feedback" in neg
    assert "Bob" in neg

    neutral = draft_reply(
        Mention(id="3", platform="mastodon", author="Charlie", mention_url="", original_text="t",
                sentiment="neutral")
    )
    assert "Charlie" in neutral


def test_draft_reply_includes_frontmatter() -> None:
    body = draft_reply(
        Mention(id="abc", platform="linkedin", author="X", mention_url="https://x",
                original_text="t", sentiment="positive")
    )
    assert "status: drafted" in body
    assert "platform: linkedin" in body


def test_build_reply_embed_color() -> None:
    busy = ReplyStats(mentions_read=3, pending=2, drafted=2)
    assert build_reply_embed(busy).color == GREEN
    waiting = ReplyStats(mentions_read=3, pending=2, drafted=0, skipped_existing=2)
    assert build_reply_embed(waiting).color == YELLOW
