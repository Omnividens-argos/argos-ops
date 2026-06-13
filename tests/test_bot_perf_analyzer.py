"""Tests unitaires de :mod:`argos_ops.agents._watchdog.perf` (ex-bot_perf_analyzer, P22.C).

Couvre la logique pure :
- ``_ratio`` : protection division par zero / None
- ``_classify`` : seuils WARN_FACTOR / REGRESSION_FACTOR
- ``collect_snapshots`` : court-circuit "insufficient samples"
- ``build_report`` : couleur globale RED/YELLOW/GREEN
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from argos_ops.agents._watchdog import perf as bot_perf_analyzer
from argos_ops.agents._watchdog.perf import (
    PerfSnapshot,
    PerfStats,
    _classify,
    _ratio,
    build_report,
    collect_snapshots,
)
from argos_ops.notifications.discord import GREEN, RED, YELLOW


def _make_snapshot(
    name: str,
    status: str,
    *,
    p95_ratio: float | None = None,
    error_ratio: float | None = None,
) -> PerfSnapshot:
    stats = PerfStats(p50_seconds=1.0, p95_seconds=2.0, error_rate=0.0, sample_size=10)
    return PerfSnapshot(
        agent_name=name,
        current=stats,
        baseline=stats,
        p95_ratio=p95_ratio,
        error_ratio=error_ratio,
        status=status,  # type: ignore[arg-type]
        reason="test",
    )


# =============================================================================
# _ratio
# =============================================================================
def test_ratio_returns_none_when_baseline_is_none() -> None:
    assert _ratio(10.0, None) is None


def test_ratio_returns_none_when_baseline_is_zero() -> None:
    assert _ratio(10.0, 0.0) is None


def test_ratio_returns_none_when_current_is_none() -> None:
    assert _ratio(None, 5.0) is None


def test_ratio_computes_division_otherwise() -> None:
    assert _ratio(10.0, 5.0) == 2.0
    assert _ratio(3.0, 2.0) == 1.5


# =============================================================================
# _classify
# =============================================================================
def test_classify_ok_when_no_ratios() -> None:
    status, reason = _classify(None, None)
    assert status == "ok"
    assert reason == "stable"


def test_classify_ok_when_below_warn() -> None:
    status, _ = _classify(1.2, 1.1)
    assert status == "ok"


def test_classify_warn_when_p95_above_warn_factor() -> None:
    status, reason = _classify(1.6, None)
    assert status == "warn"
    assert "P95" in reason


def test_classify_regression_when_p95_above_regression_factor() -> None:
    status, _ = _classify(2.5, None)
    assert status == "regression"


def test_classify_regression_when_error_ratio_critical() -> None:
    status, reason = _classify(1.0, 3.0)
    assert status == "regression"
    assert "err_rate" in reason


def test_classify_regression_wins_over_warn() -> None:
    # P95 critique + erreur warn → regression global
    status, _ = _classify(2.5, 1.6)
    assert status == "regression"


# =============================================================================
# collect_snapshots — court-circuit "insufficient samples"
# =============================================================================
@pytest.mark.asyncio
async def test_collect_snapshots_insufficient_samples_returns_ok() -> None:
    """Quand sample_size < MIN_SAMPLE_SIZE → ok + reason 'insufficient samples'."""
    session = MagicMock()
    tiny = PerfStats(p50_seconds=1.0, p95_seconds=2.0, error_rate=0.0, sample_size=2)
    with patch.object(
        bot_perf_analyzer,
        "_compute_stats",
        new=AsyncMock(side_effect=[tiny, tiny]),
    ):
        snapshots = await collect_snapshots(session, agent_names=["DigestBuilder"])
    assert len(snapshots) == 1
    assert snapshots[0].status == "ok"
    assert "insufficient samples" in snapshots[0].reason


@pytest.mark.asyncio
async def test_collect_snapshots_detects_regression_with_enough_samples() -> None:
    """Échantillon suffisant + P95 doublé → status regression."""
    session = MagicMock()
    current = PerfStats(p50_seconds=2.0, p95_seconds=4.0, error_rate=0.1, sample_size=10)
    baseline = PerfStats(p50_seconds=1.0, p95_seconds=2.0, error_rate=0.05, sample_size=10)
    with patch.object(
        bot_perf_analyzer,
        "_compute_stats",
        new=AsyncMock(side_effect=[current, baseline]),
    ):
        snapshots = await collect_snapshots(session, agent_names=["EmailBot"])
    assert snapshots[0].status == "regression"
    assert snapshots[0].p95_ratio == 2.0


# =============================================================================
# build_report — couleur globale
# =============================================================================
def test_build_report_green_when_all_ok() -> None:
    report = build_report([_make_snapshot("DigestBuilder", "ok")])
    assert report.alert_color == GREEN
    assert report.should_alert is False


def test_build_report_yellow_when_only_warn() -> None:
    report = build_report(
        [_make_snapshot("DigestBuilder", "ok"), _make_snapshot("EmailBot", "warn")]
    )
    assert report.alert_color == YELLOW
    assert report.should_alert is True


def test_build_report_red_when_any_regression() -> None:
    report = build_report(
        [
            _make_snapshot("DigestBuilder", "ok"),
            _make_snapshot("EmailBot", "warn"),
            _make_snapshot("FinanceBot", "regression"),
        ]
    )
    assert report.alert_color == RED
    assert report.should_alert is True
    assert "1 regression" in report.summary
