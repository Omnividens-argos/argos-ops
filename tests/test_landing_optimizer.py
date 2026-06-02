"""Tests LandingOptimizer."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from pydantic import SecretStr

from argos_ops.agents import landing_optimizer
from argos_ops.agents.landing_optimizer import (
    LandingMetric,
    OptimizationReport,
    build_optimizer_embed,
    collect_metrics,
    derive_proposals,
    load_metrics,
)
from argos_ops.integrations.umami import UmamiClient, UmamiPageMetric
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
        metrics=[
            LandingMetric(page="/", visits=200, conversions=1, bounce_rate=0.8, avg_time_seconds=10)
        ],
        proposals=[],  # filled later
    )
    issues.proposals = derive_proposals(issues.metrics)
    assert build_optimizer_embed(issues).color == YELLOW


# --- Wiring Umami (INFRA-02) : source canonique + fallback YAML ------------


def _configured_client() -> UmamiClient:
    return UmamiClient(
        base_url="https://analytics.omnividens.fr",
        username="admin",
        password=SecretStr("p"),
        website_id="web-1",
    )


async def test_collect_metrics_prefers_umami_when_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _configured_client()

    async def _fake_fetch(*, days: int = 30, limit: int = 25) -> list[UmamiPageMetric]:
        return [
            UmamiPageMetric(
                page="/", visits=200, conversions=1, bounce_rate=0.8, avg_time_seconds=9
            )
        ]

    monkeypatch.setattr(client, "fetch_landing_metrics", _fake_fetch)
    # Si Umami est consommé, le YAML manuel ne doit PAS être lu.
    monkeypatch.setattr(
        landing_optimizer, "load_metrics", lambda: pytest.fail("YAML ne doit pas être lu")
    )

    metrics = await collect_metrics(client)
    assert len(metrics) == 1
    assert isinstance(metrics[0], LandingMetric)
    assert (metrics[0].page, metrics[0].visits, metrics[0].conversions) == ("/", 200, 1)


async def test_collect_metrics_falls_back_to_yaml_when_not_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = UmamiClient(base_url=None, username=None, password=None, website_id=None)
    sentinel = [
        LandingMetric(page="/yaml", visits=1, conversions=0, bounce_rate=0.1, avg_time_seconds=5)
    ]
    monkeypatch.setattr(landing_optimizer, "load_metrics", lambda: sentinel)

    metrics = await collect_metrics(client)
    assert metrics[0].page == "/yaml"


async def test_collect_metrics_falls_back_when_umami_returns_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _configured_client()

    async def _empty(*, days: int = 30, limit: int = 25) -> list[UmamiPageMetric]:
        return []

    monkeypatch.setattr(client, "fetch_landing_metrics", _empty)
    sentinel = [
        LandingMetric(page="/yaml", visits=1, conversions=0, bounce_rate=0.1, avg_time_seconds=5)
    ]
    monkeypatch.setattr(landing_optimizer, "load_metrics", lambda: sentinel)

    metrics = await collect_metrics(client)
    assert metrics[0].page == "/yaml"  # 0 page Umami → fallback


async def test_collect_metrics_falls_back_when_umami_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _configured_client()

    async def _boom(*, days: int = 30, limit: int = 25) -> list[UmamiPageMetric]:
        raise RuntimeError("instance down")

    monkeypatch.setattr(client, "fetch_landing_metrics", _boom)
    sentinel = [
        LandingMetric(page="/yaml", visits=1, conversions=0, bounce_rate=0.1, avg_time_seconds=5)
    ]
    monkeypatch.setattr(landing_optimizer, "load_metrics", lambda: sentinel)

    metrics = await collect_metrics(client)
    assert metrics[0].page == "/yaml"  # exception absorbée → fallback
