"""Tests unitaires de :mod:`argos_ops.agents.contract_deadline` (P22.E)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from argos_ops.agents.contract_deadline import (
    ContractRenewal,
    _classify,
    build_report,
    load_contracts,
)
from argos_ops.notifications.discord import GREEN, RED, YELLOW


# =============================================================================
# _classify
# =============================================================================
def test_classify_urgent_under_30() -> None:
    assert _classify(15) == "urgent"
    assert _classify(30) == "urgent"


def test_classify_warn_30_60() -> None:
    assert _classify(31) == "warn"
    assert _classify(60) == "warn"


def test_classify_ok_above_60() -> None:
    assert _classify(120) == "ok"


def test_classify_expired_when_negative() -> None:
    assert _classify(-5) == "expired"


# =============================================================================
# load_contracts
# =============================================================================
def test_load_contracts_missing(tmp_path: Path) -> None:
    assert load_contracts(tmp_path / "nope.yaml") == []


def test_load_contracts_parses(tmp_path: Path) -> None:
    p = tmp_path / "c.yaml"
    p.write_text(
        "contracts:\n"
        "  - client: 'Acme'\n"
        "    start: '2025-01-15'\n"
        "    term_months: 12\n"
        "    notes: 'MSA'\n",
        encoding="utf-8",
    )
    today = date(2025, 12, 1)  # 45 jours avant renouvellement
    out = load_contracts(p, today=today)
    assert len(out) == 1
    r = out[0]
    assert r.client == "Acme"
    assert r.next_renewal == date(2026, 1, 15)
    assert r.days_left == 45
    assert r.status == "warn"


def test_load_contracts_skip_invalid_rows(tmp_path: Path) -> None:
    p = tmp_path / "c.yaml"
    p.write_text(
        "contracts:\n"
        "  - client: 'Acme'\n"  # ok
        "    start: '2025-01-15'\n"
        "    term_months: 12\n"
        "  - client: 'NoTerm'\n"  # invalid (no term_months)
        "    start: '2025-01-15'\n",
        encoding="utf-8",
    )
    out = load_contracts(p, today=date(2025, 6, 1))
    assert len(out) == 1


# =============================================================================
# build_report
# =============================================================================
def _renewal(status: str, days_left: int = 30) -> ContractRenewal:
    return ContractRenewal(
        client="x",
        start=date(2025, 1, 1),
        term_months=12,
        next_renewal=date(2026, 1, 1),
        days_left=days_left,
        status=status,  # type: ignore[arg-type]
        notes=None,
    )


def test_build_report_green_all_ok() -> None:
    report = build_report([_renewal("ok", 200)])
    assert report.alert_color == GREEN
    assert report.should_alert is False


def test_build_report_yellow_warn() -> None:
    report = build_report([_renewal("warn", 45)])
    assert report.alert_color == YELLOW


def test_build_report_red_urgent() -> None:
    report = build_report([_renewal("urgent", 20)])
    assert report.alert_color == RED
