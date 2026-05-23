"""Tests PressMonitor."""

from __future__ import annotations

from pathlib import Path

import yaml

from argos_ops.agents.press_monitor import (
    MonitorReport,
    PressMention,
    build_monitor_embed,
    load_mentions,
    mark_ack,
)
from argos_ops.notifications.discord import GREEN, ORANGE, YELLOW


def test_load_mentions_filters_invalid(tmp_path: Path) -> None:
    path = tmp_path / "m.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                "mentions": [
                    {"id": "1", "source": "ZDNet", "url": "x", "title": "t"},
                    {"source": "no-id"},
                ]
            }
        ),
        encoding="utf-8",
    )
    assert len(load_mentions(path)) == 1


def test_monitor_report_colors() -> None:
    quiet = MonitorReport(total=5, new_mentions=[], negatives=0)
    assert quiet.color == GREEN
    new_only = MonitorReport(
        total=5,
        new_mentions=[PressMention(id="1", source="x", url="", title="t")],
        negatives=0,
    )
    assert new_only.color == YELLOW
    with_neg = MonitorReport(
        total=5,
        new_mentions=[
            PressMention(id="1", source="x", url="", title="t", sentiment="negative")
        ],
        negatives=1,
    )
    assert with_neg.color == ORANGE


def test_mark_ack_rewrites_status(tmp_path: Path) -> None:
    path = tmp_path / "m.yaml"
    mentions = [
        PressMention(id="1", source="A", url="u", title="t", status="new"),
        PressMention(id="2", source="B", url="u", title="t", status="new"),
    ]
    mark_ack(mentions, ack_ids={"1"}, path=path)
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    by_id = {m["id"]: m for m in raw["mentions"]}
    assert by_id["1"]["status"] == "ack"
    assert by_id["2"]["status"] == "new"


def test_build_monitor_embed_includes_preview() -> None:
    report = MonitorReport(
        total=2,
        new_mentions=[PressMention(id="1", source="ZDNet", url="", title="Argos lance...")],
        negatives=0,
    )
    embed = build_monitor_embed(report)
    assert any("ZDNet" in f.value for f in embed.fields)
