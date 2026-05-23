"""Tests :mod:`argos_ops.agents.expense_auditor` + parser CSV."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

from argos_ops.agents.expense_auditor import (
    append_new_vendors,
    build_report,
    find_latest_csv,
    load_vendor_history,
)
from argos_ops.finance.expense_csv import (
    Anomaly,
    Expense,
    detect_anomalies,
    parse_qonto_csv,
)
from argos_ops.notifications.discord import GREEN, RED, YELLOW


# =============================================================================
# parse_qonto_csv
# =============================================================================
def test_parse_qonto_csv_supports_english_headers(tmp_path: Path) -> None:
    csv = tmp_path / "may.csv"
    csv.write_text(
        "Settlement date,Counterparty name,Total amount (EUR),Reference\n"
        "2026-05-10,OVHcloud,-12.00,hosting\n"
        "2026-05-12,Stripe,1234.56,payout\n",
        encoding="utf-8",
    )
    expenses = parse_qonto_csv(csv)
    assert len(expenses) == 2
    assert expenses[0].vendor == "OVHcloud"
    assert expenses[0].amount_eur == Decimal("-12.00")
    assert expenses[1].amount_eur == Decimal("1234.56")


def test_parse_qonto_csv_skips_malformed_rows(tmp_path: Path) -> None:
    csv = tmp_path / "broken.csv"
    csv.write_text(
        "Date,Counterparty,Amount,Label\n"
        "not-a-date,Acme,-12,bad\n"
        "2026-05-10,Acme,not-a-number,bad\n"
        "2026-05-10,,-12,no_vendor\n",
        encoding="utf-8",
    )
    assert parse_qonto_csv(csv) == []


def test_parse_qonto_csv_missing_file_returns_empty(tmp_path: Path) -> None:
    assert parse_qonto_csv(tmp_path / "nope.csv") == []


# =============================================================================
# detect_anomalies
# =============================================================================
def _exp(vendor: str, amount: str, day: int = 10) -> Expense:
    return Expense(
        settled_on=date(2026, 5, day),
        vendor=vendor,
        amount_eur=Decimal(amount),
        label=None,
    )


def test_detect_anomalies_flags_outlier() -> None:
    expenses = [
        _exp("Acme", "-10"),
        _exp("Acme", "-12"),
        _exp("BigOne", "-500"),  # 50x la médiane (~11)
    ]
    anomalies = detect_anomalies(expenses)
    kinds = {a.kind for a in anomalies}
    assert "amount_outlier" in kinds


def test_detect_anomalies_flags_duplicate() -> None:
    expenses = [
        _exp("Acme", "-100", day=10),
        _exp("Acme", "-100", day=10),  # même signature
    ]
    anomalies = detect_anomalies(expenses)
    assert any(a.kind == "duplicate" for a in anomalies)


def test_detect_anomalies_flags_new_vendor_only_with_history() -> None:
    expenses = [_exp("NewCo", "-50")]
    # Sans historique → pas de "new_vendor"
    assert detect_anomalies(expenses) == []
    # Avec historique vide → tous nouveaux
    anomalies = detect_anomalies(expenses, historic_vendors=set())
    assert any(a.kind == "new_vendor" for a in anomalies)


# =============================================================================
# build_report
# =============================================================================
def _anomaly(kind: str) -> Anomaly:
    return Anomaly(expense=_exp("X", "-50"), kind=kind, reason="test")  # type: ignore[arg-type]


def test_build_report_green_when_no_anomaly() -> None:
    report = build_report(None, [])
    assert report.alert_color == GREEN
    assert report.should_alert is False


def test_build_report_yellow_when_only_new_vendor() -> None:
    report = build_report(None, [_anomaly("new_vendor")])
    assert report.alert_color == YELLOW
    assert report.should_alert is True


def test_build_report_red_when_duplicate_or_outlier() -> None:
    report = build_report(None, [_anomaly("duplicate")])
    assert report.alert_color == RED


# =============================================================================
# vendor journal
# =============================================================================
def test_vendor_journal_round_trip(tmp_path: Path) -> None:
    assert load_vendor_history(tmp_path) == set()
    append_new_vendors(tmp_path, {"Acme", "FooCorp"})
    assert load_vendor_history(tmp_path) == {"Acme", "FooCorp"}
    # idempotent
    append_new_vendors(tmp_path, {"Acme"})
    assert load_vendor_history(tmp_path) == {"Acme", "FooCorp"}


# =============================================================================
# find_latest_csv
# =============================================================================
def test_find_latest_csv_returns_none_when_empty(tmp_path: Path) -> None:
    assert find_latest_csv(tmp_path) is None


def test_find_latest_csv_returns_most_recent(tmp_path: Path) -> None:
    older = tmp_path / "2026-04.csv"
    newer = tmp_path / "2026-05.csv"
    older.write_text("x", encoding="utf-8")
    newer.write_text("y", encoding="utf-8")
    import os
    import time

    past = time.time() - 1000
    os.utime(older, (past, past))
    assert find_latest_csv(tmp_path) == newer
