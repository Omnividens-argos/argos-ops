"""Tests unitaires de :mod:`argos_ops.agents.ci_flake_tracker` (P22.D)."""

from __future__ import annotations

from argos_ops.agents.ci_flake_tracker import (
    MIN_FAIL_RATE_PCT,
    MIN_OCCURRENCES,
    JobSample,
    build_report,
    compute_flakes,
)
from argos_ops.notifications.discord import GREEN, YELLOW


def _samples(name: str, *, total: int, failures: int) -> list[JobSample]:
    return [
        JobSample(name=name, conclusion="failure" if i < failures else "success")
        for i in range(total)
    ]


def test_compute_flakes_ignores_jobs_below_min_occurrences() -> None:
    # 2 échecs sur 10 → ratio 20% mais MIN_OCCURRENCES=3 → ignoré
    assert MIN_OCCURRENCES == 3
    flakes = compute_flakes(_samples("low-volume", total=10, failures=2))
    assert flakes == []


def test_compute_flakes_keeps_jobs_above_threshold() -> None:
    assert MIN_FAIL_RATE_PCT == 20
    flakes = compute_flakes(_samples("flaky-test", total=10, failures=5))
    assert len(flakes) == 1
    assert flakes[0].job_name == "flaky-test"
    assert flakes[0].fail_rate_pct == 50.0


def test_compute_flakes_sorts_by_fail_rate_desc() -> None:
    samples = _samples("low", total=10, failures=3) + _samples(
        "high", total=10, failures=7
    )
    flakes = compute_flakes(samples)
    assert [f.job_name for f in flakes] == ["high", "low"]


def test_build_report_green_when_no_flake() -> None:
    report = build_report([], total_runs=50)
    assert report.alert_color == GREEN
    assert report.should_alert is False


def test_build_report_yellow_when_any_flake() -> None:
    flakes = compute_flakes(_samples("flaky-test", total=10, failures=5))
    report = build_report(flakes, total_runs=50)
    assert report.alert_color == YELLOW
    assert report.should_alert is True
