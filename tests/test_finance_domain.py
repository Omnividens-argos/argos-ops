"""Tests des modules domaine du pôle Finance (archi v2, S5) — hermétiques (tmp_path)."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

from argos_ops.poles.finance import (
    accounting,
    billing,
    compliance,
    contracts,
    docs,
    expenses,
    ledger,
    reconcile,
    taxes,
    treasury,
)


def _w(root: Path, rel: str, body: str) -> None:
    p = root / "finance" / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body, encoding="utf-8")


# =============================================================================
# Billing
# =============================================================================
_SUBS = (
    "subscriptions:\n"
    "  - id: sub_a\n    customer_id: c1\n    customer_name: A\n    status: active\n"
    "    mrr_eur: 300.00\n    current_period_end: 2026-07-05\n"
    "  - id: sub_b\n    customer_id: c2\n    customer_name: B\n    status: trialing\n"
    "    mrr_eur: 200.00\n    current_period_end: 2026-08-20\n"
    "  - id: sub_c\n    customer_id: c3\n    customer_name: C\n    status: canceled\n"
    "    mrr_eur: 999.00\n    current_period_end: 2026-05-01\n"
)
_INV = (
    "invoices:\n"
    "  - id: in1\n    customer_id: c1\n    customer_name: A\n    status: open\n"
    "    amount_due_eur: 300.00\n    due_date: 2026-06-01\n"  # 17j de retard → J+15
    "  - id: in2\n    customer_id: c2\n    customer_name: B\n    status: paid\n"
    "    amount_due_eur: 0.00\n    due_date: 2026-06-01\n"
)


def test_billing_snapshot_mrr_excludes_canceled(tmp_path: Path) -> None:
    _w(tmp_path, "billing/subscriptions.yaml", _SUBS)
    _w(tmp_path, "billing/invoices.yaml", _INV)
    snap = billing.build_billing_snapshot(
        poles_root=tmp_path, now=datetime(2026, 6, 18, tzinfo=UTC)
    )
    assert snap.mrr_eur == Decimal("500.00")  # active + trialing
    assert snap.arr_eur == Decimal("6000.00")
    assert snap.n_active_subs == 2 and snap.n_subs == 3
    assert snap.n_open_invoices == 1
    assert snap.dunning[0].level == "J+15"
    assert snap.n_dunning_due == 1


def test_billing_forecast_buckets(tmp_path: Path) -> None:
    _w(tmp_path, "billing/subscriptions.yaml", _SUBS)
    fc = billing.forecast(poles_root=tmp_path, now=datetime(2026, 6, 18, tzinfo=UTC))
    # sub_a renouvelle dans la fenêtre 30j (07-05), sub_b dans la fenêtre 90j
    # (08-20 > today+60), sub_c exclu (canceled).
    assert fc.expected_30d_eur == Decimal("300.00")
    assert fc.expected_90d_eur == Decimal("200.00")
    assert fc.n_subs_considered == 2


def test_draft_dunning_shadow_and_not_due(tmp_path: Path) -> None:
    _w(tmp_path, "billing/invoices.yaml", _INV)
    path = billing.draft_dunning("in1", poles_root=tmp_path, now=datetime(2026, 6, 18, tzinfo=UTC))
    assert path is not None and path.exists()
    assert "shadow" in path.read_text(encoding="utf-8")
    # Facture payée → rien à relancer.
    assert billing.draft_dunning("in2", poles_root=tmp_path) is None
    assert billing.draft_dunning("ghost", poles_root=tmp_path) is None


# =============================================================================
# Treasury
# =============================================================================
def test_treasury_runway_alert(tmp_path: Path) -> None:
    _w(
        tmp_path,
        "treasury/state.yaml",
        "cash_balance_eur: 48000\nmonthly_burn_eur: 9500\nmonthly_revenue_eur: 1200\n"
        "snapshot_date: 2026-06-15\nburn_cap_eur: 12000\n",
    )
    report = treasury.burn_report(poles_root=tmp_path)
    assert report.snapshot is not None
    assert report.runway_months == Decimal("5.8")
    assert report.severity == "alert" and report.should_alert is True


def test_treasury_absent(tmp_path: Path) -> None:
    report = treasury.burn_report(poles_root=tmp_path)
    assert report.snapshot is None and report.should_alert is False


# =============================================================================
# Expenses
# =============================================================================
def test_expenses_outlier_and_new_vendor(tmp_path: Path) -> None:
    _w(
        tmp_path,
        "expenses/2026-06.csv",
        "Settlement date,Counterparty name,Total amount (EUR),Reference\n"
        "2026-06-02,OVHcloud,-12.00,Heberg\n"
        "2026-06-03,GitHub,-21.00,Team\n"
        "2026-06-08,URSSAF,-1800.00,Cotis\n"
        "2026-06-10,Anthropic,-90.00,Claude\n",
    )
    _w(tmp_path, "expenses/vendors.md", "# Vendors\n\n- Anthropic\n- GitHub\n- OVHcloud\n")
    report = expenses.audit(poles_root=tmp_path)
    kinds = {a.kind for a in report.anomalies}
    assert "amount_outlier" in kinds  # URSSAF 1800 > 3x médiane
    assert "new_vendor" in kinds  # URSSAF jamais vu
    assert report.severity == "alert"


def test_expenses_no_csv(tmp_path: Path) -> None:
    report = expenses.audit(poles_root=tmp_path)
    assert report.anomalies == [] and report.severity == "ok"


# =============================================================================
# Reconcile
# =============================================================================
def test_reconcile_orphan_payout(tmp_path: Path) -> None:
    _w(
        tmp_path,
        "reconcile/payouts.yaml",
        "payouts:\n  - id: po1\n    arrival_date: 2026-06-05\n    amount_eur: 420.00\n"
        "  - id: po2\n    arrival_date: 2026-06-10\n    amount_eur: 999.00\n",
    )
    _w(
        tmp_path,
        "expenses/2026-06.csv",
        "Settlement date,Counterparty name,Total amount (EUR),Reference\n"
        "2026-06-05,Stripe,420.00,Payout\n",
    )
    report = reconcile.reconcile_report(poles_root=tmp_path)
    assert len(report.matches) == 1
    assert len(report.orphan_payouts) == 1 and report.orphan_payouts[0].id == "po2"


# =============================================================================
# Contracts
# =============================================================================
def test_vendor_and_client_contracts(tmp_path: Path) -> None:
    _w(
        tmp_path,
        "contracts/vendors.yaml",
        "contracts:\n  - vendor: OVH\n    renewal_date: 2026-09-01\n    notice_period_days: 60\n"
        "    monthly_cost_eur: 12\n",
    )
    _w(
        tmp_path,
        "contracts/clients.yaml",
        "contracts:\n  - client: Acme\n    start: 2025-07-01\n    term_months: 12\n",
    )
    today = date(2026, 6, 18)
    vendors = contracts.vendor_contracts(poles_root=tmp_path, today=today)
    assert vendors[0].status == "urgent"  # deadline 2026-07-03 → 15j
    clients = contracts.client_renewals(poles_root=tmp_path, today=today)
    assert clients[0].status == "urgent"  # renouvellement 2026-07-01 → 13j


# =============================================================================
# Taxes
# =============================================================================
def test_ca3_from_mrr_proxy(tmp_path: Path) -> None:
    _w(tmp_path, "billing/subscriptions.yaml", _SUBS)
    ca3 = taxes.current_ca3(poles_root=tmp_path, period_month="2026-05")
    assert ca3.ca_ht_eur == Decimal("500.00")
    assert ca3.tva_collected_eur == Decimal("100.00")  # 20 %


def test_fiscal_calendar_sorted_and_in_horizon() -> None:
    cal = taxes.fiscal_calendar(today=date(2026, 6, 18), horizon_days=120)
    assert cal, "au moins une échéance attendue dans 120j"
    assert all(0 <= d.days_until <= 120 for d in cal)
    assert cal == sorted(cal, key=lambda d: d.due_date)
    # CA3 du mois M-1 due le 19 du mois courant.
    assert any(d.kind == "tva_ca3" and d.due_date == date(2026, 6, 19) for d in cal)


def test_fiscal_calendar_large_horizon_not_truncated() -> None:
    # Le nombre de CA3 doit suivre l'horizon (pas figé à 6 mois). Régression S5.
    cal = taxes.fiscal_calendar(today=date(2026, 6, 18), horizon_days=300)
    assert all(0 <= d.days_until <= 300 for d in cal)
    # Une CA3 dont la butoir tombe à ~6 mois (période 2026-12, due 2027-01-19) doit y être.
    assert any(d.kind == "tva_ca3" and d.due_date == date(2027, 1, 19) for d in cal)


def test_fiscal_calendar_december_rollover() -> None:
    cal = taxes.fiscal_calendar(today=date(2026, 12, 20), horizon_days=120)
    # CA3 de décembre (M-1=2026-11 due 2026-12-19 est passée ; 2026-12 due 2027-01-19).
    assert any(d.kind == "tva_ca3" and d.due_date == date(2027, 1, 19) for d in cal)


# =============================================================================
# Compliance (garde-fou)
# =============================================================================
_RGPD_OK = (
    "traitements:\n"
    "  - nom: Prospection\n    base_legale: intérêt légitime\n    finalite: prospection\n"
    "    donnees: [email]\n    duree_conservation: 3 ans\n    review_date: 2026-06-01\n"
)
_AIACT_OK = "systemes:\n  - nom: FinanceAgent\n    risk_class: minimal\n"


def test_rgpd_conforme_not_blocking(tmp_path: Path) -> None:
    _w(tmp_path, "compliance/rgpd_registry.yaml", _RGPD_OK)
    _w(tmp_path, "compliance/ai_act_registry.yaml", _AIACT_OK)
    rgpd = compliance.load_rgpd_registry(poles_root=tmp_path, today=date(2026, 6, 18))
    assert rgpd.present and not rgpd.should_alert and rgpd.gaps == []
    assert compliance.compliance_blocking(poles_root=tmp_path, today=date(2026, 6, 18)) is False


def test_rgpd_gap_blocks(tmp_path: Path) -> None:
    _w(
        tmp_path,
        "compliance/rgpd_registry.yaml",
        "traitements:\n  - nom: Sans base\n    finalite: x\n    donnees: [email]\n"
        "    duree_conservation: 1 an\n    review_date: 2026-06-01\n",
    )
    _w(tmp_path, "compliance/ai_act_registry.yaml", _AIACT_OK)
    rgpd = compliance.load_rgpd_registry(poles_root=tmp_path, today=date(2026, 6, 18))
    assert rgpd.should_alert and len(rgpd.gaps) == 1
    assert compliance.compliance_blocking(poles_root=tmp_path, today=date(2026, 6, 18)) is True


def test_rgpd_stale_review_blocks(tmp_path: Path) -> None:
    _w(
        tmp_path,
        "compliance/rgpd_registry.yaml",
        "traitements:\n  - nom: Vieux\n    base_legale: contrat\n    finalite: x\n"
        "    donnees: [email]\n    duree_conservation: 1 an\n    review_date: 2024-01-01\n",
    )
    _w(tmp_path, "compliance/ai_act_registry.yaml", _AIACT_OK)
    assert compliance.compliance_blocking(poles_root=tmp_path, today=date(2026, 6, 18)) is True


def test_ai_act_prohibited_blocks(tmp_path: Path) -> None:
    _w(tmp_path, "compliance/rgpd_registry.yaml", _RGPD_OK)
    _w(
        tmp_path,
        "compliance/ai_act_registry.yaml",
        "systemes:\n  - nom: Bad\n    risk_class: prohibited\n",
    )
    ai = compliance.load_ai_act_registry(poles_root=tmp_path)
    assert ai.prohibited and ai.should_alert
    assert compliance.compliance_blocking(poles_root=tmp_path, today=date(2026, 6, 18)) is True


def test_registries_absent_block(tmp_path: Path) -> None:
    assert compliance.compliance_blocking(poles_root=tmp_path, today=date(2026, 6, 18)) is True
    assert compliance.blocking_reason(poles_root=tmp_path, today=date(2026, 6, 18))


def test_empty_ai_act_blocks(tmp_path: Path) -> None:
    # Registre AI Act présent mais vide = obligation de transparence non remplie →
    # bloque (symétrie avec RGPD vide). Régression de la revue adversariale S5.
    _w(tmp_path, "compliance/rgpd_registry.yaml", _RGPD_OK)
    _w(tmp_path, "compliance/ai_act_registry.yaml", "systemes: []\n")
    ai = compliance.load_ai_act_registry(poles_root=tmp_path)
    assert ai.present and ai.should_alert and not ai.prohibited
    assert compliance.compliance_blocking(poles_root=tmp_path, today=date(2026, 6, 18)) is True
    assert "AI Act" in compliance.blocking_reason(poles_root=tmp_path, today=date(2026, 6, 18))


def test_unclassified_ai_act_alerts_but_does_not_block(tmp_path: Path) -> None:
    # unclassified = gap de documentation (alerte) mais PAS un interdit art. 5 → non bloquant.
    _w(tmp_path, "compliance/rgpd_registry.yaml", _RGPD_OK)
    _w(
        tmp_path,
        "compliance/ai_act_registry.yaml",
        "systemes:\n  - nom: X\n    risk_class: bogus\n",
    )
    ai = compliance.load_ai_act_registry(poles_root=tmp_path)
    assert ai.should_alert and ai.unclassified and not ai.prohibited
    assert compliance.compliance_blocking(poles_root=tmp_path, today=date(2026, 6, 18)) is False


def test_empty_rgpd_blocks(tmp_path: Path) -> None:
    _w(tmp_path, "compliance/rgpd_registry.yaml", "traitements: []\n")
    _w(tmp_path, "compliance/ai_act_registry.yaml", _AIACT_OK)
    assert compliance.compliance_blocking(poles_root=tmp_path, today=date(2026, 6, 18)) is True


# =============================================================================
# Ledger
# =============================================================================
def test_ledger_add_delete_summary(tmp_path: Path) -> None:
    f1 = ledger.add_flow(
        flow_date=date(2026, 6, 1),
        label="Vente",
        category="revenue",
        direction="in",
        amount_eur=Decimal("700"),
        poles_root=tmp_path,
    )
    ledger.add_flow(
        flow_date=date(2026, 6, 2),
        label="Hébergement",
        category="hosting",
        direction="out",
        amount_eur=Decimal("12"),
        poles_root=tmp_path,
    )
    flows = ledger.load_flows(poles_root=tmp_path)
    assert len(flows) == 2
    summ = ledger.summarize(flows)
    assert summ.total_in_eur == Decimal("700.00")
    assert summ.total_out_eur == Decimal("12.00")
    assert summ.net_eur == Decimal("688.00")
    # Idempotent : ré-ajouter f1 ne duplique pas.
    ledger.add_flow(
        flow_date=date(2026, 6, 1),
        label="Vente",
        category="revenue",
        direction="in",
        amount_eur=Decimal("700"),
        poles_root=tmp_path,
    )
    assert len(ledger.load_flows(poles_root=tmp_path)) == 2
    assert ledger.delete_flow(f1.id, poles_root=tmp_path) is True
    assert ledger.delete_flow("ghost", poles_root=tmp_path) is False
    assert len(ledger.load_flows(poles_root=tmp_path)) == 1


# =============================================================================
# Docs + accounting
# =============================================================================
def test_generate_ca3_doc(tmp_path: Path) -> None:
    _w(tmp_path, "billing/subscriptions.yaml", _SUBS)
    path = docs.generate_ca3(poles_root=tmp_path, period_month="2026-05")
    assert path.exists() and path.name == "ca3_2026-05.md"
    assert docs.read_doc("ca3_2026-05.md", poles_root=tmp_path)
    assert any(d.kind == "ca3" for d in docs.list_docs(poles_root=tmp_path))


def test_generate_proposal_requires_context(tmp_path: Path) -> None:
    assert docs.generate_proposal("ghost", poles_root=tmp_path) is None
    _w(
        tmp_path,
        "docs/contexts/acme.yaml",
        "deal_id: acme\ncompany: Acme\ncontact_name: Marc\ncontact_email: m@acme.fr\n"
        "plan: Argos Pro\nmonthly_price_eur: 350\nissue_date: 2026-06-18\n",
    )
    path = docs.generate_proposal("acme", poles_root=tmp_path)
    assert path is not None and path.exists()
    assert "acme" in docs.list_context_ids(poles_root=tmp_path)


def test_read_doc_anti_traversal(tmp_path: Path) -> None:
    assert docs.read_doc("../../etc/passwd", poles_root=tmp_path) is None
    assert docs.read_doc("nope.md", poles_root=tmp_path) is None


def test_read_doc_rejects_reserved_subdirs(tmp_path: Path) -> None:
    # read_doc est restreint aux enfants directs de docs/ : un .md dans uploads/
    # n'est pas lisible (ni via / ni via \\ sur Windows). Régression S5.
    docs.save_upload("secret.md", "contenu confidentiel", poles_root=tmp_path)
    assert "secret.md" in docs.list_uploads(poles_root=tmp_path)
    assert docs.read_doc("uploads/secret.md", poles_root=tmp_path) is None
    assert docs.read_doc("uploads\\secret.md", poles_root=tmp_path) is None


def test_accounting_csv(tmp_path: Path) -> None:
    ledger.add_flow(
        flow_date=date(2026, 6, 1),
        label="Vente",
        category="revenue",
        direction="in",
        amount_eur=Decimal("700"),
        poles_root=tmp_path,
    )
    csv_text = accounting.build_accounting_csv(poles_root=tmp_path)
    assert "solde_eur" in csv_text and "Vente" in csv_text and "700.00" in csv_text
    path = accounting.export_accounting(poles_root=tmp_path, today=date(2026, 6, 18))
    assert path.exists() and path.name == "export_comptable_2026-06-18.csv"
