"""Tests unitaires de :mod:`argos_ops.agents.okr_tracker` (P22.E)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from argos_ops.agents.okr_tracker import (
    KeyResult,
    build_report,
    classify,
    load_okr,
    prorata,
    quarter_bounds,
)
from argos_ops.notifications.discord import GREEN, RED, YELLOW


# =============================================================================
# quarter_bounds / prorata
# =============================================================================
def test_quarter_bounds_q2() -> None:
    start, end = quarter_bounds(2026, 2)
    assert start == date(2026, 4, 1)
    assert end == date(2026, 6, 30)


def test_quarter_bounds_invalid() -> None:
    with pytest.raises(ValueError):
        quarter_bounds(2026, 5)


def test_prorata_start_of_quarter() -> None:
    assert prorata(date(2026, 4, 1), year=2026, quarter=2) == 0.0


def test_prorata_end_of_quarter() -> None:
    assert prorata(date(2026, 6, 30), year=2026, quarter=2) == 1.0


def test_prorata_mid_quarter() -> None:
    p = prorata(date(2026, 5, 16), year=2026, quarter=2)
    assert 0.4 < p < 0.6


# =============================================================================
# classify
# =============================================================================
def test_classify_completed() -> None:
    assert classify(1.0, 0.5) == "completed"
    assert classify(1.2, 0.5) == "completed"


def test_classify_on_track() -> None:
    assert classify(0.45, 0.5) == "on_track"
    assert classify(0.5, 0.5) == "on_track"


def test_classify_at_risk() -> None:
    assert classify(0.3, 0.5) == "at_risk"


def test_classify_off_track() -> None:
    assert classify(0.1, 0.5) == "off_track"


def test_classify_no_penalty_at_start() -> None:
    """expected < 5% (début du trimestre) → toujours on_track."""
    assert classify(0.0, 0.02) == "on_track"


# =============================================================================
# load_okr
# =============================================================================
def test_load_okr_missing(tmp_path: Path) -> None:
    report = load_okr(tmp_path / "nope.yaml", today=date(2026, 5, 23))
    assert report.alert_color == RED
    assert "introuvable" in report.summary


def test_load_okr_parses(tmp_path: Path) -> None:
    p = tmp_path / "okr.yaml"
    p.write_text(
        "quarter: '2026-Q2'\n"
        "year: 2026\n"
        "quarter_num: 2\n"
        "objectives:\n"
        "  - title: 'MRR'\n"
        "    key_results:\n"
        "      - name: 'MRR'\n"
        "        target: 10000\n"
        "        actual: 4500\n"
        "        unit: EUR\n",
        encoding="utf-8",
    )
    report = load_okr(p, today=date(2026, 5, 16))
    assert len(report.key_results) == 1
    kr = report.key_results[0]
    assert kr.target == 10000
    assert kr.actual == 4500


def test_load_okr_skips_target_zero(tmp_path: Path) -> None:
    p = tmp_path / "okr.yaml"
    p.write_text(
        "quarter: '2026-Q2'\n"
        "year: 2026\n"
        "objectives:\n"
        "  - title: 'x'\n"
        "    key_results:\n"
        "      - name: 'invalid'\n"
        "        target: 0\n"
        "        actual: 0\n",
        encoding="utf-8",
    )
    report = load_okr(p, today=date(2026, 5, 16))
    assert report.key_results == []


# =============================================================================
# build_report
# =============================================================================
def _kr(status: str) -> KeyResult:
    return KeyResult(
        objective="x",
        name="k",
        target=10,
        actual=5,
        unit="",
        status=status,  # type: ignore[arg-type]
        progress_pct=0.5,
        expected_pct=0.5,
    )


def test_build_report_green_all_on_track() -> None:
    report = build_report([_kr("on_track")], quarter="2026-Q2")
    assert report.alert_color == GREEN


def test_build_report_yellow_at_risk() -> None:
    report = build_report([_kr("at_risk")], quarter="2026-Q2")
    assert report.alert_color == YELLOW


def test_build_report_red_off_track() -> None:
    report = build_report(
        [_kr("on_track"), _kr("off_track")], quarter="2026-Q2"
    )
    assert report.alert_color == RED
