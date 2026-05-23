"""Tests unitaires de ``argos_ops.sales.templates`` (P22.H Sales Sprint 3)."""

from __future__ import annotations

from datetime import date

from argos_ops.sales.models import ProposalContext
from argos_ops.sales.templates import (
    render_contract,
    render_demo_followup,
    render_proposal,
)

CTX = ProposalContext(
    deal_id="acme-q2-2026",
    company="Acme SA",
    contact_name="Marc Dupont",
    contact_email="marc@acme.fr",
    siret="12345678900012",
    plan="Argos Pro",
    monthly_price_eur=350,
    setup_fee_eur=500,
    discount_percent=10,
    contract_duration_months=12,
    issue_date=date(2026, 5, 23),
    validity_days=30,
)


def test_render_proposal_includes_pricing_and_discount() -> None:
    md = render_proposal(CTX)
    assert "Acme SA" in md
    assert "Marc Dupont" in md
    assert "350 €" in md  # monthly
    assert "4200 €" in md  # annual subscription 350*12
    assert "10 %" in md  # discount
    # subtotal 4200+500=4700, discount 470 → total 4230, tva 846, ttc 5076
    assert "4230 €" in md
    assert "5076 €" in md


def test_render_proposal_without_discount_no_discount_row() -> None:
    ctx_no_discount = ProposalContext(
        deal_id="x",
        company="X",
        contact_name="Y",
        contact_email="y@x.fr",
        discount_percent=0,
        issue_date=date(2026, 5, 23),
    )
    md = render_proposal(ctx_no_discount)
    assert "Remise commerciale" not in md


def test_render_contract_mentions_siret_clause() -> None:
    md = render_contract(CTX)
    assert "SIRET 12345678900012" in md
    assert "Article 1" in md and "Article 5" in md
    assert "12 mois" in md


def test_render_demo_followup_uses_owners_in_steps() -> None:
    body = render_demo_followup(
        first_name="Marc",
        when=date(2026, 5, 23),
        pain_points=["audit RGPD"],
        next_steps=[("Argos", "envoyer devis"), ("Marc", "valider budget")],
        attachments=["devis.pdf"],
        focus_topic="intégration GitLab",
        next_milestone="vendredi",
    )
    assert "**Argos** : envoyer devis" in body
    assert "**Marc** : valider budget" in body
    assert "audit RGPD" in body
    assert "devis.pdf" in body
    assert "intégration GitLab" in body
