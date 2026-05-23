"""Tests unitaires TrendSpotter."""

from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path
from unittest.mock import patch

import yaml

from argos_ops.agents.trend_spotter import TrendDigest, build_trend_embed, write_digest
from argos_ops.marketing.trends import TrendItem, load_trend_sources, score_trends
from argos_ops.notifications.discord import GREEN, YELLOW


def _yaml_dump(items: list[dict[str, object]]) -> str:
    return yaml.safe_dump({"items": items})


def test_load_trend_sources_returns_empty_if_missing(tmp_path: Path) -> None:
    assert load_trend_sources(path=tmp_path / "nope.yaml") == []


def test_load_trend_sources_parses_valid_entries(tmp_path: Path) -> None:
    path = tmp_path / "sources.yaml"
    path.write_text(
        _yaml_dump(
            [
                {
                    "title": "Faille X",
                    "url": "https://cert.fr/X",
                    "published_at": "2026-05-22",
                    "keywords": ["cve", "supply"],
                    "weight": 1.5,
                },
                {
                    "title": "Sans date",
                    "url": "https://x",
                    "published_at": "not-a-date",
                },
            ]
        ),
        encoding="utf-8",
    )
    items = load_trend_sources(path=path)
    assert len(items) == 1
    assert items[0].title == "Faille X"
    assert items[0].weight == 1.5


def test_score_trends_keeps_fresh_orders_by_score() -> None:
    today = datetime.now(UTC).date()
    items = [
        TrendItem(title="fresh", url="u1", published_at=today, weight=1.0),
        TrendItem(title="old", url="u2", published_at=date(2020, 1, 1), weight=10.0),
        TrendItem(title="mid", url="u3", published_at=today.replace(day=max(1, today.day - 5)) if today.day > 5 else today, weight=0.5),
    ]
    scored = score_trends(items, lookback_days=14)
    titles = [i.title for i in scored]
    assert "old" not in titles
    assert scored[0].score >= scored[-1].score


def test_write_digest_creates_markdown(tmp_path: Path) -> None:
    with patch("argos_ops.agents.trend_spotter.DIGEST_DIR", tmp_path):
        path = write_digest(["Item A", "Item B"], now=datetime(2026, 5, 23, tzinfo=UTC))
    content = path.read_text(encoding="utf-8")
    assert "1. Item A" in content
    assert "2. Item B" in content


def test_build_trend_embed_color() -> None:
    yellow = build_trend_embed(TrendDigest(top=[], total_fresh=0, digest_path=None))
    assert yellow.color == YELLOW
    green = build_trend_embed(TrendDigest(top=["A"], total_fresh=1, digest_path=None))
    assert green.color == GREEN
