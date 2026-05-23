"""Tests unitaires SocialAnalytics."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import yaml

from argos_ops.agents.social_analytics import (
    AnalyticsRun,
    ChannelReport,
    aggregate,
    build_analytics_embed,
)
from argos_ops.marketing.analytics import EngagementMetrics, load_engagement_window
from argos_ops.notifications.discord import GREEN, YELLOW


def test_channel_report_ratios_safe_on_zero_impressions() -> None:
    r = ChannelReport(channel="linkedin")
    assert r.ctr == 0.0
    assert r.engagement_rate == 0.0


def test_aggregate_groups_by_platform() -> None:
    now = datetime.now(UTC)
    metrics = [
        EngagementMetrics(posted_at=now, platform="linkedin", url="u1", impressions=1000, engagements=50, clicks=20),
        EngagementMetrics(posted_at=now, platform="linkedin", url="u2", impressions=500, engagements=10, clicks=5),
        EngagementMetrics(posted_at=now, platform="mastodon", url="u3", impressions=200, engagements=8, clicks=1),
    ]
    run = aggregate(metrics, window_days=7)
    assert set(run.by_channel) == {"linkedin", "mastodon"}
    li = run.by_channel["linkedin"]
    assert li.posts == 2
    assert li.impressions == 1500
    assert li.clicks == 25


def test_analytics_run_weak_signal_when_ctr_low() -> None:
    run = AnalyticsRun(
        window_days=7,
        by_channel={"linkedin": ChannelReport(channel="linkedin", posts=2, impressions=1000, engagements=10, clicks=5)},
    )
    # CTR = 0.5% (< 1%), ER = 1% (< 2%) — weak
    assert run.has_weak_signal is True


def test_analytics_run_strong_signal() -> None:
    run = AnalyticsRun(
        window_days=7,
        by_channel={"linkedin": ChannelReport(channel="linkedin", posts=2, impressions=1000, engagements=30, clicks=20)},
    )
    assert run.has_weak_signal is False


def test_build_analytics_embed_color() -> None:
    weak = AnalyticsRun(
        window_days=7,
        by_channel={"x": ChannelReport(channel="x", posts=1, impressions=1000, engagements=5, clicks=2)},
    )
    assert build_analytics_embed(weak).color == YELLOW
    strong = AnalyticsRun(
        window_days=7,
        by_channel={"x": ChannelReport(channel="x", posts=1, impressions=1000, engagements=50, clicks=30)},
    )
    assert build_analytics_embed(strong).color == GREEN


def test_load_engagement_window_filters_old(tmp_path: Path) -> None:
    path = tmp_path / "engagement.yaml"
    now = datetime.now(UTC)
    path.write_text(
        yaml.safe_dump(
            {
                "posts": [
                    {
                        "posted_at": (now - timedelta(days=2)).isoformat(),
                        "platform": "linkedin",
                        "url": "u1",
                        "impressions": 100,
                        "engagements": 5,
                        "clicks": 1,
                    },
                    {
                        "posted_at": (now - timedelta(days=30)).isoformat(),
                        "platform": "linkedin",
                        "url": "u2",
                        "impressions": 9999,
                        "engagements": 999,
                        "clicks": 999,
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    metrics = load_engagement_window(days=7, path=path)
    assert len(metrics) == 1
    assert metrics[0].impressions == 100
