"""Tests :mod:`argos_ops.agents.invoice_predictor` + helper cash_flow."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from argos_ops.agents.invoice_predictor import (
    render_forecast_markdown,
    write_forecast,
)
from argos_ops.finance.cash_flow import forecast_cash_flow
from argos_ops.integrations.stripe_client import StripeSubscription


def _sub(
    sub_id: str,
    *,
    status: str,
    mrr_eur: str,
    period_end: datetime | None,
) -> StripeSubscription:
    return StripeSubscription(
        id=sub_id,
        customer_id=f"cus_{sub_id}",
        customer_email=None,
        customer_name=None,
        status=status,
        mrr_eur=Decimal(mrr_eur),
        currency="eur",
        interval="month",
        created_at=datetime(2025, 1, 1, tzinfo=UTC),
        current_period_end=period_end,
    )


def test_forecast_buckets_by_renewal_date() -> None:
    now = datetime(2026, 5, 23, tzinfo=UTC)
    subs = [
        _sub("a", status="active", mrr_eur="100.00", period_end=now + timedelta(days=10)),
        _sub("b", status="active", mrr_eur="200.00", period_end=now + timedelta(days=45)),
        _sub("c", status="trialing", mrr_eur="50.00", period_end=now + timedelta(days=80)),
        _sub("d", status="active", mrr_eur="300.00", period_end=now + timedelta(days=120)),
    ]
    fc = forecast_cash_flow(subs, as_of=now)
    assert fc.expected_30d_eur == Decimal("100.00")
    assert fc.expected_60d_eur == Decimal("200.00")
    assert fc.expected_90d_eur == Decimal("50.00")
    assert fc.n_subs_considered == 4
    assert fc.n_subs_excluded == 0


def test_forecast_excludes_past_due() -> None:
    now = datetime(2026, 5, 23, tzinfo=UTC)
    subs = [
        _sub("a", status="active", mrr_eur="100.00", period_end=now + timedelta(days=10)),
        _sub("b", status="past_due", mrr_eur="200.00", period_end=now + timedelta(days=10)),
        _sub("c", status="canceled", mrr_eur="50.00", period_end=now + timedelta(days=10)),
    ]
    fc = forecast_cash_flow(subs, as_of=now)
    assert fc.n_subs_considered == 1
    assert fc.n_subs_excluded == 2
    assert fc.expected_30d_eur == Decimal("100.00")


def test_forecast_treats_missing_period_end_as_30d() -> None:
    now = datetime(2026, 5, 23, tzinfo=UTC)
    subs = [_sub("a", status="active", mrr_eur="100.00", period_end=None)]
    fc = forecast_cash_flow(subs, as_of=now)
    assert fc.expected_30d_eur == Decimal("100.00")


def test_render_forecast_markdown_mentions_amounts() -> None:
    now = datetime(2026, 5, 23, tzinfo=UTC)
    subs = [
        _sub("a", status="active", mrr_eur="123.45", period_end=now + timedelta(days=10)),
    ]
    fc = forecast_cash_flow(subs, as_of=now)
    md = render_forecast_markdown(fc)
    assert "123.45" in md
    assert "2026-05-23" in md


def test_write_forecast_creates_file(tmp_path: Path) -> None:
    now = datetime(2026, 5, 23, tzinfo=UTC)
    subs = [_sub("a", status="active", mrr_eur="100.00", period_end=now)]
    fc = forecast_cash_flow(subs, as_of=now)
    target = write_forecast(fc, target_dir=tmp_path)
    assert target.exists()
    assert target.name == "forecast_2026-05-23.md"
    assert "100" in target.read_text(encoding="utf-8")
