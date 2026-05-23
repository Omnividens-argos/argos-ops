"""Tests LandingOptimizer."""

from __future__ import annotations

from pathlib import Path

import yaml

from argos_ops.agents.landing_optimizer import (
    LandingMetric,
    OptimizationReport,
    build_optimizer_embed,
    derive_proposals,
    load_metrics,
)
from argos_ops.notifications.discord import GREEN, YELLOW


def test_load_metrics_skips_invalid(tmp_path: Path) -> None:
    path = tmp_path / "p.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                "pages": [
                    {
                        "page": "/",
                        "visits": 1000,
                        "conversions": 5,
                        "bounce_rate": 0.5,
                        "avg_time_seconds": 30,
                    },
                    {"page": "bad"},  # missing fields
                    "not-a-dict",
                ]
            }
        ),
        encoding="utf-8",
    )
    metrics = load_metrics(path)
    assert len(metrics) == 1
    assert metrics[0].page == "/"


def test_derive_proposals_flags_low_cr_high_bounce_short_time() -> None:
    metrics = [
        LandingMetric(page="/", visits=200, conversions=1, bounce_rate=0.80, avg_time_seconds=15),
    ]
    props = derive_proposals(metrics)
    issues = [p.issue for p in props]
    assert any("CR" in i for i in issues)
    assert any("Bounce" in i for i in issues)
    assert any("Time on page" in i for i in issues)


def test_derive_proposals_silent_on_healthy_metrics() -> None:
    metrics = [
        LandingMetric(page="/", visits=200, conversions=10, bounce_rate=0.40, avg_time_seconds=60),
    ]
    assert derive_proposals(metrics) == []


def test_build_optimizer_embed_color() -> None:
    empty = OptimizationReport(metrics=[], proposals=[])
    assert build_optimizer_embed(empty).color == GREEN
    issues = OptimizationReport(
        metrics=[LandingMetric(page="/", visits=200, conversions=1, bounce_rate=0.8, avg_time_seconds=10)],
        proposals=[],  # filled later
    )
    issues.proposals = derive_proposals(issues.metrics)
    assert build_optimizer_embed(issues).color == YELLOW
