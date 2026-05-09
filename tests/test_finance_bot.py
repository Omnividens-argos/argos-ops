"""Tests unitaires du FinanceBot (P7).

Couvrent les calculs déterministes (MRR, classification dunning, rendu
templates, formatage stats). Les calls Stripe + SMTP réels sont validés
en intégration (test live avec compte Stripe test).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from argos_ops.agents.finance_bot import (
    DUNNING_TEMPLATES,
    FinanceStats,
    build_finance_embed,
    render_dunning_email,
)
from argos_ops.integrations.stripe_client import (
    StripeInvoice,
    StripeSubscription,
    classify_dunning_level,
    compute_arr_eur,
    compute_mrr_eur,
)
from argos_ops.notifications.discord import GREEN, RED, YELLOW


# =============================================================================
# Fixtures
# =============================================================================
def _sub(status: str, mrr_eur: Decimal) -> StripeSubscription:
    return StripeSubscription(
        id=f"sub_{status}_{mrr_eur}",
        customer_id="cus_test",
        customer_email="x@y.fr",
        customer_name="Test",
        status=status,
        mrr_eur=mrr_eur,
        currency="eur",
        interval="month",
        created_at=datetime.now(UTC),
        current_period_end=None,
    )


def _invoice(*, status: str, due_offset_days: int | None) -> StripeInvoice:
    due = (
        datetime.now(UTC) - timedelta(days=due_offset_days) if due_offset_days is not None else None
    )
    return StripeInvoice(
        id="in_test_42",
        customer_id="cus_42",
        customer_email="client@bigco.fr",
        customer_name="Big Co",
        status=status,
        amount_due_eur=Decimal("249.00"),
        due_date=due,
        created_at=datetime.now(UTC) - timedelta(days=30),
        attempt_count=2,
        hosted_invoice_url="https://invoice.stripe.com/test/42",
    )


# =============================================================================
# compute_mrr_eur
# =============================================================================
def test_compute_mrr_eur_only_active_and_trialing_count() -> None:
    subs = [
        _sub("active", Decimal("249.00")),
        _sub("trialing", Decimal("39.00")),
        _sub("canceled", Decimal("129.00")),  # ignoré
        _sub("past_due", Decimal("249.00")),  # ignoré
        _sub("incomplete", Decimal("39.00")),  # ignoré
    ]
    mrr = compute_mrr_eur(subs)
    assert mrr == Decimal("288.00")


def test_compute_mrr_eur_empty_returns_zero() -> None:
    assert compute_mrr_eur([]) == Decimal("0.00")


def test_compute_arr_eur_is_mrr_times_12() -> None:
    assert compute_arr_eur(Decimal("100.00")) == Decimal("1200.00")
    assert compute_arr_eur(Decimal("0.00")) == Decimal("0.00")


# =============================================================================
# classify_dunning_level
# =============================================================================
def test_classify_dunning_paid_invoice_is_none() -> None:
    inv = _invoice(status="paid", due_offset_days=10)
    assert classify_dunning_level(inv) == "none"


def test_classify_dunning_no_due_date_is_none() -> None:
    inv = _invoice(status="open", due_offset_days=None)
    assert classify_dunning_level(inv) == "none"


def test_classify_dunning_under_3_days_is_none() -> None:
    inv = _invoice(status="open", due_offset_days=2)
    assert classify_dunning_level(inv) == "none"


def test_classify_dunning_3_to_6_days_is_j_plus_3() -> None:
    inv = _invoice(status="open", due_offset_days=3)
    assert classify_dunning_level(inv) == "J+3"
    inv2 = _invoice(status="open", due_offset_days=6)
    assert classify_dunning_level(inv2) == "J+3"


def test_classify_dunning_7_to_14_days_is_j_plus_7() -> None:
    inv = _invoice(status="open", due_offset_days=7)
    assert classify_dunning_level(inv) == "J+7"
    inv2 = _invoice(status="open", due_offset_days=14)
    assert classify_dunning_level(inv2) == "J+7"


def test_classify_dunning_15_plus_days_is_j_plus_15() -> None:
    inv = _invoice(status="open", due_offset_days=15)
    assert classify_dunning_level(inv) == "J+15"
    inv2 = _invoice(status="open", due_offset_days=60)
    assert classify_dunning_level(inv2) == "J+15"


# =============================================================================
# render_dunning_email
# =============================================================================
def test_render_dunning_email_none_returns_none() -> None:
    inv = _invoice(status="paid", due_offset_days=10)
    assert render_dunning_email("none", inv) is None


def test_render_dunning_email_j3_amical() -> None:
    inv = _invoice(status="open", due_offset_days=4)
    rendered = render_dunning_email("J+3", inv)
    assert rendered is not None
    subject, body = rendered
    assert "Petit rappel" in subject
    assert inv.id in subject
    assert "249.00" in body
    assert "https://invoice.stripe.com/test/42" in body


def test_render_dunning_email_j7_ferme() -> None:
    inv = _invoice(status="open", due_offset_days=10)
    rendered = render_dunning_email("J+7", inv)
    assert rendered is not None
    subject, body = rendered
    assert "impayée" in subject.lower()
    assert "régulariser" in body.lower()


def test_render_dunning_email_j15_escalade() -> None:
    inv = _invoice(status="open", due_offset_days=20)
    rendered = render_dunning_email("J+15", inv)
    assert rendered is not None
    subject, body = rendered
    assert "Suspension" in subject
    assert "48 h" in body


def test_dunning_templates_cover_all_levels() -> None:
    """Sanity : on a un template pour chaque niveau de dunning canonique."""
    assert set(DUNNING_TEMPLATES.keys()) == {"J+3", "J+7", "J+15"}


# =============================================================================
# FinanceStats.summary
# =============================================================================
def test_finance_stats_summary_format() -> None:
    stats = FinanceStats(
        n_subs=10,
        n_active_subs=8,
        mrr_eur=Decimal("1992.00"),
        arr_eur=Decimal("23904.00"),
        mrr_delta_pct=2.5,
        n_open_invoices=3,
        n_dunning_sent_j3=2,
        n_dunning_sent_j7=1,
        n_dunning_sent_j15=0,
        n_companies_synced=10,
    )
    summary = stats.summary()
    assert "mrr=1992.00" in summary
    assert "arr=23904.00" in summary
    assert "mrr_delta=+2.5%" in summary
    assert "active_subs=8/10" in summary
    assert "open_inv=3" in summary
    assert "dunning_sent_3=2" in summary


def test_finance_stats_summary_no_baseline() -> None:
    """Sans baseline MRR (premier run), le delta est omis."""
    stats = FinanceStats(mrr_eur=Decimal("100.00"), arr_eur=Decimal("1200.00"))
    summary = stats.summary()
    assert "mrr_delta" not in summary


# =============================================================================
# build_finance_embed — couleur
# =============================================================================
def test_build_finance_embed_green_when_clean() -> None:
    stats = FinanceStats(n_subs=5, n_active_subs=5, mrr_eur=Decimal("249"), mrr_delta_pct=1.0)
    embed = build_finance_embed(stats)
    assert embed.color == GREEN


def test_build_finance_embed_yellow_when_open_invoices() -> None:
    stats = FinanceStats(n_subs=5, n_active_subs=5, n_open_invoices=2)
    embed = build_finance_embed(stats)
    assert embed.color == YELLOW


def test_build_finance_embed_red_when_mrr_drops_more_than_5_pct() -> None:
    stats = FinanceStats(mrr_eur=Decimal("900"), mrr_delta_pct=-7.5)
    embed = build_finance_embed(stats)
    assert embed.color == RED


def test_build_finance_embed_baseline_unavailable_fallback() -> None:
    """Sans baseline, le texte affiche un fallback explicite."""
    stats = FinanceStats(mrr_eur=Decimal("100.00"))
    embed = build_finance_embed(stats)
    mrr_field = next(f for f in embed.fields if f.name == "MRR")
    assert "indisponible" in mrr_field.value


# =============================================================================
# Sanity garde-fous
# =============================================================================
@pytest.mark.parametrize("level", ["J+3", "J+7", "J+15"])
def test_dunning_templates_have_required_placeholders(level: str) -> None:
    """Chaque template doit pouvoir être rendu avec invoice_id / amount /
    due_date / invoice_url sans ``KeyError``."""
    tpl = DUNNING_TEMPLATES[level]  # type: ignore[index]
    ctx = {
        "invoice_id": "in_42",
        "amount": "249.00",
        "due_date": "01/01/2026",
        "invoice_url": "https://x",
    }
    tpl["subject"].format(**ctx)
    tpl["body"].format(**ctx)
