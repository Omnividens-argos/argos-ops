"""Tests KeywordRadar."""

from __future__ import annotations

from pathlib import Path

import yaml

from argos_ops.agents.keyword_radar import (
    KeywordMovement,
    RadarReport,
    build_radar_embed,
    diff_positions,
    load_history,
    load_keywords,
    save_history,
)
from argos_ops.notifications.discord import GREEN, YELLOW


def test_load_keywords_filters_priority(tmp_path: Path) -> None:
    path = tmp_path / "kw.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                "keywords": [
                    {"term": "pentest", "position": 5, "priority": "high"},
                    {"term": "obscure", "position": 99, "priority": "low"},
                    {"term": "no-pos", "priority": "high"},
                ]
            }
        ),
        encoding="utf-8",
    )
    kws = load_keywords(path)
    assert kws == {"pentest": 5}


def test_diff_positions_marks_new_and_moves() -> None:
    moves = diff_positions({"a": 5, "b": 10}, {"a": 12})
    by_kw = {m.keyword: m for m in moves}
    assert by_kw["a"].delta == 7  # monté de 7 places (12 → 5)
    assert by_kw["b"].is_new is True
    assert by_kw["b"].delta == 0


def test_radar_report_should_alert_on_3_losses() -> None:
    report = RadarReport(
        movements=[
            KeywordMovement(keyword="a", current=20, previous=10),
            KeywordMovement(keyword="b", current=30, previous=15),
            KeywordMovement(keyword="c", current=25, previous=12),
            KeywordMovement(keyword="d", current=5, previous=5),
        ]
    )
    assert report.losses_over_5 == 3
    assert report.should_alert is True


def test_save_and_load_history_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "h.yaml"
    save_history({"x": 7, "y": 12}, path=path)
    assert load_history(path) == {"x": 7, "y": 12}


def test_build_radar_embed_color() -> None:
    quiet = RadarReport(movements=[KeywordMovement(keyword="a", current=5, previous=5)])
    assert build_radar_embed(quiet).color == GREEN
    noisy = RadarReport(
        movements=[
            KeywordMovement(keyword=f"k{i}", current=20, previous=10) for i in range(3)
        ]
    )
    assert build_radar_embed(noisy).color == YELLOW
