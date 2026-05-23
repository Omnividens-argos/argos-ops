"""Tests :mod:`argos_ops.agents.vendor_contract_watcher`."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

from argos_ops.agents.vendor_contract_watcher import (
    Contract,
    build_report,
    load_contracts,
)
from argos_ops.notifications.discord import GREEN, RED, YELLOW


def _contract(days_until_deadline: int, vendor: str = "Acme") -> Contract:
    today = date(2026, 5, 23)
    deadline = today + timedelta(days=days_until_deadline)
    from argos_ops.agents.vendor_contract_watcher import _classify

    return Contract(
        vendor=vendor,
        renewal_date=deadline + timedelta(days=30),
        notice_period_days=30,
        monthly_cost_eur=Decimal("100.00"),
        notes=None,
        deadline_date=deadline,
        days_until_deadline=days_until_deadline,
        status=_classify(days_until_deadline),
    )


# =============================================================================
# build_report
# =============================================================================
def test_build_report_green_when_all_ok() -> None:
    report = build_report([_contract(120, "Acme"), _contract(180, "Foo")])
    assert report.alert_color == GREEN
    assert report.should_alert is False


def test_build_report_yellow_when_approaching() -> None:
    # 45j until deadline → status="approaching"
    report = build_report([_contract(45, "Acme")])
    assert report.alert_color == YELLOW
    assert report.should_alert is True


def test_build_report_red_when_urgent() -> None:
    # 10j until deadline → status="urgent"
    report = build_report([_contract(10, "Acme")])
    assert report.alert_color == RED


def test_build_report_red_when_missed() -> None:
    # -3j until deadline → status="missed"
    report = build_report([_contract(-3, "Acme")])
    assert report.alert_color == RED


# =============================================================================
# load_contracts
# =============================================================================
def test_load_contracts_missing_file_returns_empty(tmp_path: Path) -> None:
    assert load_contracts(tmp_path / "nope.yaml") == []


def test_load_contracts_parses_valid_yaml(tmp_path: Path) -> None:
    path = tmp_path / "c.yaml"
    path.write_text(
        "contracts:\n"
        "  - vendor: OVHcloud\n"
        "    renewal_date: 2026-09-01\n"
        "    notice_period_days: 60\n"
        "    monthly_cost_eur: 12.00\n"
        "    notes: hosting\n",
        encoding="utf-8",
    )
    contracts = load_contracts(path, today=date(2026, 5, 23))
    assert len(contracts) == 1
    c = contracts[0]
    assert c.vendor == "OVHcloud"
    assert c.renewal_date == date(2026, 9, 1)
    assert c.deadline_date == date(2026, 7, 3)  # 60j avant 2026-09-01


def test_load_contracts_skips_missing_fields(tmp_path: Path) -> None:
    path = tmp_path / "c.yaml"
    path.write_text(
        "contracts:\n"
        "  - vendor: Acme\n"  # pas de renewal_date
        "  - renewal_date: 2026-09-01\n",  # pas de vendor
        encoding="utf-8",
    )
    assert load_contracts(path) == []
