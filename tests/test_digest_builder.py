"""Tests unitaires du DigestBuilder.

Couvrent uniquement le formatting et la couleur — la collecte KPIs Postgres
et le push HTTP Discord sont testés en intégration séparée (à venir P19).
"""

from __future__ import annotations

from datetime import UTC, datetime

from argos_ops.agents.digest_builder import (
    DigestKPIs,
    _format_leads_breakdown,
    build_digest_embed,
)
from argos_ops.notifications.discord import GREEN, RED, YELLOW


# =============================================================================
# Fixtures locales (pas de DB — pure logic)
# =============================================================================
def _kpis_clean() -> DigestKPIs:
    return DigestKPIs(
        leads_total=0,
        leads_by_source={},
        new_customers=0,
        open_tickets=0,
        pending_human_tickets=0,
        active_breakers=[],
    )


def _kpis_with_escalation() -> DigestKPIs:
    return DigestKPIs(
        leads_total=12,
        leads_by_source={"inbound_chat": 8, "outbound": 3, "ad_lead": 1},
        new_customers=1,
        open_tickets=4,
        pending_human_tickets=2,
        active_breakers=[],
    )


def _kpis_with_breaker() -> DigestKPIs:
    return DigestKPIs(
        leads_total=5,
        leads_by_source={"inbound_chat": 5},
        new_customers=0,
        open_tickets=1,
        pending_human_tickets=0,
        active_breakers=["EmailBot"],
    )


# =============================================================================
# Couleur d'embed
# =============================================================================
def test_build_digest_embed_green() -> None:
    embed = build_digest_embed(_kpis_clean())
    assert embed.color == GREEN


def test_build_digest_embed_yellow_when_pending_human() -> None:
    embed = build_digest_embed(_kpis_with_escalation())
    assert embed.color == YELLOW


def test_build_digest_embed_red_when_breaker_active() -> None:
    embed = build_digest_embed(_kpis_with_breaker())
    assert embed.color == RED


# =============================================================================
# Contenu d'embed
# =============================================================================
def test_build_digest_embed_title_iso_date() -> None:
    today = datetime(2026, 5, 8, 8, 0, tzinfo=UTC)
    embed = build_digest_embed(_kpis_clean(), today=today)
    assert embed.title == "Argos — Digest 2026-05-08"


def test_build_digest_embed_mrr_unbranched_before_p7() -> None:
    embed = build_digest_embed(_kpis_clean())
    mrr_field = next(f for f in embed.fields if f.name == "MRR")
    assert "Stripe non branché" in mrr_field.value


def test_build_digest_embed_mrr_branched() -> None:
    kpis = _kpis_clean()
    kpis.mrr_eur = 1234
    kpis.mrr_delta_pct = 5.0
    embed = build_digest_embed(kpis)
    mrr_field = next(f for f in embed.fields if f.name == "MRR")
    assert "1 234 €" in mrr_field.value
    assert "+5.0%" in mrr_field.value


def test_build_digest_embed_breakers_listed() -> None:
    embed = build_digest_embed(_kpis_with_breaker())
    breakers_field = next(f for f in embed.fields if f.name == "Breakers actifs")
    assert "EmailBot" in breakers_field.value


def test_build_digest_embed_breakers_none_means_aucun() -> None:
    embed = build_digest_embed(_kpis_clean())
    breakers_field = next(f for f in embed.fields if f.name == "Breakers actifs")
    assert breakers_field.value == "aucun"


def test_build_digest_embed_tickets_includes_pending_human() -> None:
    embed = build_digest_embed(_kpis_with_escalation())
    tickets_field = next(f for f in embed.fields if f.name == "Tickets ouverts")
    assert "4" in tickets_field.value
    assert "2 à traiter humain" in tickets_field.value


# =============================================================================
# Leads breakdown
# =============================================================================
def test_format_leads_breakdown_empty() -> None:
    assert _format_leads_breakdown({}) == "0"


def test_format_leads_breakdown_single_source() -> None:
    assert _format_leads_breakdown({"inbound_chat": 5}) == "5 (5 inbound_chat)"


def test_format_leads_breakdown_multi_source_sorted_by_volume() -> None:
    result = _format_leads_breakdown({"inbound_chat": 8, "outbound": 3, "ad_lead": 1})
    # 12 total, ordre décroissant par volume
    assert result.startswith("12 (")
    assert "8 inbound_chat" in result
    # inbound_chat doit apparaître avant outbound (8 > 3)
    assert result.index("8 inbound_chat") < result.index("3 outbound")
