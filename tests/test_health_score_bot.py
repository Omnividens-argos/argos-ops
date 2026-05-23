"""Tests unitaires de ``argos_ops.agents.health_score`` (P22.G)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import yaml

from argos_ops.agents.health_score import (
    _persist_snapshot,
    build_health_embed,
    build_report,
)
from argos_ops.cs.models import HealthBand, HealthScore


def test_build_report_aggregates_bands() -> None:
    scores = [
        HealthScore("a", 85, HealthBand.GREEN, ["usage 60%"]),
        HealthScore("b", 50, HealthBand.YELLOW, ["NPS passif"]),
        HealthScore("c", 25, HealthBand.RED, ["inactif 45j", "NPS détracteur"]),
    ]
    report = build_report(scores)
    assert report.green == 1
    assert report.yellow == 1
    assert report.red == 1
    assert report.average == 53
    assert report.worst[0].customer_id == "c"


def test_build_health_embed_red_when_any_red() -> None:
    scores = [HealthScore("c", 25, HealthBand.RED, ["alerte"])]
    embed = build_health_embed(build_report(scores))
    assert embed.color == 0xE74C3C


def test_build_health_embed_green_when_all_green() -> None:
    scores = [HealthScore("a", 90, HealthBand.GREEN, ["sain"])]
    embed = build_health_embed(build_report(scores))
    assert embed.color == 0x2ECC71


def test_persist_snapshot_writes_yaml(tmp_path: Path) -> None:
    scores = [HealthScore("a", 80, HealthBand.GREEN, ["usage 60%"])]
    path = tmp_path / "snapshot_2026-05-23.yaml"
    _persist_snapshot(path, scores, day=date(2026, 5, 23))
    assert path.exists()
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert raw["snapshot_date"] == "2026-05-23"
    assert raw["scores"][0]["band"] == "green"
    assert raw["scores"][0]["drivers"] == ["usage 60%"]
