"""Tests du script ``SocialAnalyticsScript`` (Marketing, archi v2, S2). Hermétique."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import yaml

from argos_ops.marketing.analytics import load_engagement_window
from argos_ops.poles.base import run_script
from argos_ops.poles.marketing.scripts.social_analytics import (
    SocialAnalyticsScript,
    aggregate_engagement,
)


def _write_engagement(path: Path) -> None:
    today = datetime.now(UTC).date().isoformat()
    posts = [
        # linkedin : fort
        {
            "posted_at": f"{today}T08:00:00Z",
            "platform": "linkedin",
            "url": "u1",
            "impressions": 1000,
            "engagements": 80,
            "clicks": 30,
        },
        # mastodon : faible (CTR < 1% et ER < 2%)
        {
            "posted_at": f"{today}T09:00:00Z",
            "platform": "mastodon",
            "url": "u2",
            "impressions": 1000,
            "engagements": 5,
            "clicks": 2,
        },
    ]
    path.write_text(yaml.safe_dump({"posts": posts}), encoding="utf-8")


async def test_writes_engagement_facts_with_weak_flag(tmp_path: Path) -> None:
    eng = tmp_path / "engagement.yaml"
    _write_engagement(eng)

    result = await run_script(SocialAnalyticsScript(poles_root=tmp_path, engagement_path=eng))

    assert result.status == "success"
    assert len(result.written) == 2
    assert all(r.kind == "engagement" for r in result.written)
    weak = [r for r in result.written if r.important]
    assert len(weak) == 1
    assert "mastodon" in weak[0].tags
    assert "weak" in weak[0].tags


async def test_empty_engagement_writes_nothing(tmp_path: Path) -> None:
    result = await run_script(
        SocialAnalyticsScript(poles_root=tmp_path, engagement_path=tmp_path / "absent.yaml")
    )
    assert result.status == "success"
    assert result.written == []


def test_aggregate_helper(tmp_path: Path) -> None:
    eng = tmp_path / "engagement.yaml"
    _write_engagement(eng)
    metrics = load_engagement_window(days=7, path=eng)
    by_channel = aggregate_engagement(metrics)
    assert by_channel["linkedin"].is_weak is False
    assert by_channel["mastodon"].is_weak is True
