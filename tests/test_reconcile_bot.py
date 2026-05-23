"""Tests :mod:`argos_ops.agents.reconcile_bot` + helper reconcile."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from argos_ops.agents.reconcile_bot import build_run_report
from argos_ops.finance.expense_csv import Expense
from argos_ops.finance.reconcile import (
    StripePayout,
    parse_payouts_yaml_entries,
    reconcile,
)
from argos_ops.notifications.discord import GREEN, RED, YELLOW


def _payout(pid: str, day: int, amount: str) -> StripePayout:
    return StripePayout(
        id=pid, arrival_date=date(2026, 5, day), amount_eur=Decimal(amount)
    )


def _qonto_credit(day: int, amount: str, *, vendor: str = "STRIPE TRANSFER") -> Expense:
    return Expense(
        settled_on=date(2026, 5, day),
        vendor=vendor,
        amount_eur=Decimal(amount),
        label=None,
    )


# =============================================================================
# reconcile (matcher heuristique)
# =============================================================================
def test_reconcile_matches_payout_within_window() -> None:
    payouts = [_payout("po_1", 10, "1234.56")]
    expenses = [_qonto_credit(12, "1234.56")]
    report = reconcile(payouts, expenses)
    assert len(report.matches) == 1
    assert report.matches[0].delta_days == 2


def test_reconcile_rejects_out_of_window() -> None:
    payouts = [_payout("po_1", 10, "100.00")]
    expenses = [_qonto_credit(20, "100.00")]
    report = reconcile(payouts, expenses)
    assert report.matches == []
    assert len(report.orphan_payouts) == 1


def test_reconcile_rejects_amount_mismatch() -> None:
    payouts = [_payout("po_1", 10, "100.00")]
    expenses = [_qonto_credit(11, "99.50")]
    report = reconcile(payouts, expenses)
    assert report.matches == []


def test_reconcile_ignores_non_stripe_credits() -> None:
    payouts = [_payout("po_1", 10, "100.00")]
    expenses = [_qonto_credit(11, "100.00", vendor="Random Wire")]
    report = reconcile(payouts, expenses)
    assert report.matches == []
    assert report.orphan_payouts == payouts


def test_reconcile_each_credit_consumed_at_most_once() -> None:
    payouts = [_payout("po_1", 10, "100.00"), _payout("po_2", 11, "100.00")]
    expenses = [_qonto_credit(12, "100.00")]
    report = reconcile(payouts, expenses)
    assert len(report.matches) == 1


# =============================================================================
# parse_payouts_yaml_entries
# =============================================================================
def test_parse_payouts_yaml_entries_handles_iso_date() -> None:
    entries = [{"id": "po_1", "arrival_date": "2026-05-10", "amount_eur": "100.00"}]
    payouts = parse_payouts_yaml_entries(entries)
    assert len(payouts) == 1
    assert payouts[0].arrival_date == date(2026, 5, 10)


def test_parse_payouts_yaml_entries_skips_invalid() -> None:
    entries = [
        {"id": None, "arrival_date": "2026-05-10", "amount_eur": "100"},
        {"id": "po_1", "arrival_date": "garbage", "amount_eur": "100"},
        {"id": "po_2"},
    ]
    assert parse_payouts_yaml_entries(entries) == []


# =============================================================================
# build_run_report
# =============================================================================
def test_build_run_report_green_on_all_matched() -> None:
    payouts = [_payout("po_1", 10, "100.00")]
    expenses = [_qonto_credit(11, "100.00")]
    report = reconcile(payouts, expenses)
    run_report = build_run_report(report)
    assert run_report.alert_color == GREEN
    assert run_report.should_alert is False


def test_build_run_report_yellow_on_orphan_credit() -> None:
    payouts: list[StripePayout] = []
    expenses = [_qonto_credit(11, "100.00")]
    report = reconcile(payouts, expenses)
    run_report = build_run_report(report)
    assert run_report.alert_color == YELLOW
    assert run_report.should_alert is True


def test_build_run_report_red_on_orphan_payout() -> None:
    payouts = [_payout("po_1", 10, "100.00")]
    expenses: list[Expense] = []
    report = reconcile(payouts, expenses)
    run_report = build_run_report(report)
    assert run_report.alert_color == RED
