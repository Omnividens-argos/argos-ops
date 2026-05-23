"""Tests :mod:`argos_ops.agents.burn_rate_monitor`."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

from argos_ops.agents.burn_rate_monitor import (
    DEFAULT_BURN_CAP_EUR,
    TreasurySnapshot,
    build_report,
    load_treasury,
)
from argos_ops.notifications.discord import GREEN, RED, YELLOW


def _snap(
    cash: str = "100000.00",
    burn: str = "5000.00",
    rev: str = "0.00",
    *,
    cap: Decimal = DEFAULT_BURN_CAP_EUR,
) -> TreasurySnapshot:
    return TreasurySnapshot(
        cash_balance_eur=Decimal(cash),
        monthly_burn_eur=Decimal(burn),
        monthly_revenue_eur=Decimal(rev),
        snapshot_date=date(2026, 5, 20),
        burn_cap_eur=cap,
    )


# =============================================================================
# build_report
# =============================================================================
def test_build_report_silence_when_snapshot_missing() -> None:
    report = build_report(None)
    assert report.should_alert is False
    assert report.alert_color == GREEN


def test_build_report_silence_when_cashflow_positive() -> None:
    report = build_report(_snap(cash="50000", burn="2000", rev="3000"))
    assert report.should_alert is False
    assert report.runway_months is None  # rev > burn → no finite runway


def test_build_report_green_when_runway_above_9_months() -> None:
    # cash 100k, net_burn 5k/m → runway = 20 mois
    report = build_report(_snap(cash="100000", burn="5000", rev="0"))
    assert report.alert_color == GREEN
    assert report.should_alert is False


def test_build_report_yellow_between_6_and_9_months() -> None:
    # cash 35k, net_burn 5k/m → runway = 7 mois
    report = build_report(_snap(cash="35000", burn="5000", rev="0"))
    assert report.alert_color == YELLOW


def test_build_report_red_below_6_months() -> None:
    # cash 20k, net_burn 5k/m → runway = 4 mois
    report = build_report(_snap(cash="20000", burn="5000", rev="0"))
    assert report.alert_color == RED


def test_build_report_red_when_burn_above_cap() -> None:
    # runway 20m mais burn 15k > cap 12k → alerte rouge
    report = build_report(_snap(cash="300000", burn="15000", rev="0"))
    assert report.alert_color == RED


# =============================================================================
# load_treasury
# =============================================================================
def test_load_treasury_missing_file_returns_none(tmp_path: Path) -> None:
    assert load_treasury(tmp_path / "nope.yaml") is None


def test_load_treasury_parses_valid_yaml(tmp_path: Path) -> None:
    path = tmp_path / "t.yaml"
    path.write_text(
        "cash_balance_eur: 80000\n"
        "monthly_burn_eur: 8500.50\n"
        "monthly_revenue_eur: 3200\n"
        "snapshot_date: 2026-05-20\n",
        encoding="utf-8",
    )
    snap = load_treasury(path)
    assert snap is not None
    assert snap.cash_balance_eur == Decimal("80000")
    assert snap.monthly_burn_eur == Decimal("8500.50")
    assert snap.snapshot_date == date(2026, 5, 20)
