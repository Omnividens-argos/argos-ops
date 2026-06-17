"""Endpoints cockpit du pôle **Finance & Conformité** (archi v2, S5).

Sert au shell ``poles.html`` tout l'onglet Finance, 100 % fichiers / local-first
(D-017) — tout est recalculé à chaud depuis les fichiers ``data/poles/finance/…`` :

- ``GET  /api/poles/finance/overview``           — facturation (MRR/ARR + dunning),
  forecast 30/60/90j, trésorerie (burn/runway), tableur des flux, dépenses,
  rapprochement, contrats (fournisseurs/clients), échéancier fiscal, registres
  RGPD + AI Act, incidents, docs générés, compteurs.
- ``GET  /api/poles/finance/docs/{name}``        — contenu markdown d'un doc (preview).
- ``POST /api/poles/finance/ledger/flows``       — ajoute une ligne au tableur.
- ``DELETE /api/poles/finance/ledger/flows/{id}``— supprime une ligne du tableur.
- ``POST /api/poles/finance/docs/generate``      — génère CA3 / devis / contrat
  (409 si la conformité gèle l'onboarding — « Python tranche »).
- ``POST /api/poles/finance/docs/upload``        — enregistre un doc à remplir.
- ``POST /api/poles/finance/invoices/{id}/dunning`` — drafte une relance (shadow).
- ``POST /api/poles/finance/export/accounting``  — produit l'export comptable CSV.

``POLES_DIR`` est un global de module → patchable en test.
"""

from __future__ import annotations

import math
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from argos_ops.poles.config import POLES_DIR
from argos_ops.poles.finance import (
    accounting,
    billing,
    compliance,
    contracts,
    docs,
    expenses,
    incidents,
    ledger,
    reconcile,
    taxes,
    treasury,
)

router = APIRouter(prefix="/api/poles/finance", tags=["poles", "finance"])


def _f(value: Decimal | None) -> float | None:
    return float(value) if value is not None else None


# =============================================================================
# Schemas — sortie
# =============================================================================
class DunningOut(BaseModel):
    invoice_id: str
    customer: str
    amount_due_eur: float
    due_date: date | None
    level: str
    drafted: bool


class BillingOut(BaseModel):
    mrr_eur: float
    arr_eur: float
    n_subs: int
    n_active_subs: int
    n_open_invoices: int
    open_amount_eur: float
    dunning: list[DunningOut]


class ForecastOut(BaseModel):
    expected_30d_eur: float
    expected_60d_eur: float
    expected_90d_eur: float
    n_subs_considered: int


class TreasuryOut(BaseModel):
    present: bool
    cash_balance_eur: float | None
    monthly_burn_eur: float | None
    monthly_revenue_eur: float | None
    net_burn_eur: float
    runway_months: float | None
    severity: str
    summary: str


class FlowOut(BaseModel):
    id: str
    flow_date: date
    label: str
    category: str
    direction: str
    amount_eur: float
    balance_eur: float


class MonthNet(BaseModel):
    month: str
    net_eur: float


class CategoryNet(BaseModel):
    category: str
    net_eur: float


class LedgerOut(BaseModel):
    flows: list[FlowOut]
    total_in_eur: float
    total_out_eur: float
    net_eur: float
    by_month: list[MonthNet]
    by_category: list[CategoryNet]


class AnomalyOut(BaseModel):
    vendor: str
    kind: str
    amount_eur: float
    settled_on: date
    reason: str


class ExpensesOut(BaseModel):
    source_csv: str | None
    severity: str
    summary: str
    anomalies: list[AnomalyOut]


class ReconcileOut(BaseModel):
    matched: int
    orphan_payouts: int
    orphan_credits: int
    summary: str


class VendorContractOut(BaseModel):
    vendor: str
    renewal_date: date
    deadline_date: date
    days_until: int
    status: str
    monthly_cost_eur: float


class ClientContractOut(BaseModel):
    client: str
    next_renewal: date
    days_left: int
    status: str


class ContractsOut(BaseModel):
    vendors: list[VendorContractOut]
    clients: list[ClientContractOut]


class FiscalDeadlineOut(BaseModel):
    kind: str
    label: str
    due_date: date
    days_until: int


class TreatmentOut(BaseModel):
    nom: str
    base_legale: str
    finalite: str
    donnees: list[str]
    review_date: date | None
    conforme: bool
    issues: list[str]


class RgpdOut(BaseModel):
    present: bool
    should_alert: bool
    summary: str
    treatments: list[TreatmentOut]


class AiActSystemOut(BaseModel):
    nom: str
    role: str
    risk: str


class AiActOut(BaseModel):
    present: bool
    should_alert: bool
    summary: str
    counts: dict[str, int]
    systems: list[AiActSystemOut]


class IncidentOut(BaseModel):
    slug: str
    title: str
    date: str
    category: str
    severity: str
    status: str


class DocOut(BaseModel):
    name: str
    kind: str
    has_pdf: bool


class FinanceCounts(BaseModel):
    mrr_eur: float
    open_invoices: int
    dunning_due: int
    runway_months: float | None
    rgpd_gaps: int
    ai_act_prohibited: int
    ai_act_unclassified: int
    contracts_urgent: int
    expense_anomalies: int
    reconcile_orphans: int
    incidents_open: int
    fiscal_next_days: int | None
    compliance_blocking: bool


class FinanceOverview(BaseModel):
    pole: str
    generated_at: datetime
    billing: BillingOut
    forecast: ForecastOut
    treasury: TreasuryOut
    ledger: LedgerOut
    expenses: ExpensesOut
    reconcile: ReconcileOut
    contracts: ContractsOut
    fiscal: list[FiscalDeadlineOut]
    rgpd: RgpdOut
    ai_act: AiActOut
    incidents: list[IncidentOut]
    docs: list[DocOut]
    uploads: list[str]
    contexts: list[str]
    compliance_blocking: bool
    compliance_reason: str
    counts: FinanceCounts


# =============================================================================
# Schemas — entrée
# =============================================================================
class FlowPayload(BaseModel):
    flow_date: date
    label: str
    category: str = "autre"
    direction: str = "in"
    amount_eur: float


class GenerateDocPayload(BaseModel):
    kind: str  # ca3 | proposal | contract
    deal_id: str | None = None


class UploadPayload(BaseModel):
    filename: str
    content: str = ""


class DocGenResult(BaseModel):
    name: str
    kind: str
    has_pdf: bool


class DunningResult(BaseModel):
    invoice_id: str
    status: str
    draft_path: str


class ExportResult(BaseModel):
    path: str
    csv: str


class DocContent(BaseModel):
    name: str
    content: str


# =============================================================================
# Route — lecture
# =============================================================================
@router.get("/overview", response_model=FinanceOverview)
async def get_overview() -> FinanceOverview:
    """Tout ce dont l'onglet Finance a besoin en un seul fetch."""
    today = date.today()
    snap = billing.build_billing_snapshot(poles_root=POLES_DIR)
    fc = billing.forecast(poles_root=POLES_DIR)
    burn = treasury.burn_report(poles_root=POLES_DIR)
    flows = ledger.load_flows(poles_root=POLES_DIR)
    summary = ledger.summarize(flows)
    expense_report = expenses.audit(poles_root=POLES_DIR, update_history=False)
    recon = reconcile.reconcile_report(poles_root=POLES_DIR)
    vendor_contracts = contracts.vendor_contracts(poles_root=POLES_DIR, today=today)
    client_renewals = contracts.client_renewals(poles_root=POLES_DIR, today=today)
    calendar = taxes.fiscal_calendar(today=today)
    rgpd = compliance.load_rgpd_registry(poles_root=POLES_DIR, today=today)
    ai_act = compliance.load_ai_act_registry(poles_root=POLES_DIR)
    incident_items = incidents.list_incidents(poles_root=POLES_DIR)
    doc_items = docs.list_docs(poles_root=POLES_DIR)
    upload_items = docs.list_uploads(poles_root=POLES_DIR)
    context_ids = docs.list_context_ids(poles_root=POLES_DIR)
    blocking = compliance.compliance_blocking(poles_root=POLES_DIR, today=today)
    reason = compliance.blocking_reason(poles_root=POLES_DIR, today=today)

    # Tableur avec solde cumulé.
    flow_out: list[FlowOut] = []
    balance = Decimal("0.00")
    for fl in flows:
        balance += fl.signed_eur
        flow_out.append(
            FlowOut(
                id=fl.id,
                flow_date=fl.flow_date,
                label=fl.label,
                category=fl.category,
                direction=fl.direction,
                amount_eur=float(fl.amount_eur),
                balance_eur=float(balance),
            )
        )

    counts = FinanceCounts(
        mrr_eur=float(snap.mrr_eur),
        open_invoices=snap.n_open_invoices,
        dunning_due=snap.n_dunning_due,
        runway_months=_f(burn.runway_months),
        rgpd_gaps=len(rgpd.gaps),
        ai_act_prohibited=len(ai_act.prohibited),
        ai_act_unclassified=len(ai_act.unclassified),
        contracts_urgent=sum(1 for c in vendor_contracts if c.status in ("urgent", "missed"))
        + sum(1 for r in client_renewals if r.status in ("urgent", "expired")),
        expense_anomalies=len(expense_report.anomalies),
        reconcile_orphans=len(recon.orphan_payouts) + len(recon.orphan_credits),
        incidents_open=sum(1 for i in incident_items if i.status == "open"),
        fiscal_next_days=(calendar[0].days_until if calendar else None),
        compliance_blocking=blocking,
    )

    return FinanceOverview(
        pole="finance",
        generated_at=datetime.now(UTC),
        billing=BillingOut(
            mrr_eur=float(snap.mrr_eur),
            arr_eur=float(snap.arr_eur),
            n_subs=snap.n_subs,
            n_active_subs=snap.n_active_subs,
            n_open_invoices=snap.n_open_invoices,
            open_amount_eur=float(snap.open_amount_eur),
            dunning=[
                DunningOut(
                    invoice_id=d.invoice_id,
                    customer=d.customer_name or d.customer_id or "—",
                    amount_due_eur=float(d.amount_due_eur),
                    due_date=d.due_date,
                    level=d.level,
                    drafted=d.drafted,
                )
                for d in snap.dunning
            ],
        ),
        forecast=ForecastOut(
            expected_30d_eur=float(fc.expected_30d_eur),
            expected_60d_eur=float(fc.expected_60d_eur),
            expected_90d_eur=float(fc.expected_90d_eur),
            n_subs_considered=fc.n_subs_considered,
        ),
        treasury=TreasuryOut(
            present=burn.snapshot is not None,
            cash_balance_eur=_f(burn.snapshot.cash_balance_eur) if burn.snapshot else None,
            monthly_burn_eur=_f(burn.snapshot.monthly_burn_eur) if burn.snapshot else None,
            monthly_revenue_eur=_f(burn.snapshot.monthly_revenue_eur) if burn.snapshot else None,
            net_burn_eur=float(burn.net_burn_eur),
            runway_months=_f(burn.runway_months),
            severity=burn.severity,
            summary=burn.summary,
        ),
        ledger=LedgerOut(
            flows=flow_out,
            total_in_eur=float(summary.total_in_eur),
            total_out_eur=float(summary.total_out_eur),
            net_eur=float(summary.net_eur),
            by_month=[MonthNet(month=m, net_eur=float(n)) for m, n in summary.by_month],
            by_category=[CategoryNet(category=c, net_eur=float(n)) for c, n in summary.by_category],
        ),
        expenses=ExpensesOut(
            source_csv=(expense_report.source_csv.name if expense_report.source_csv else None),
            severity=expense_report.severity,
            summary=expense_report.summary,
            anomalies=[
                AnomalyOut(
                    vendor=a.expense.vendor,
                    kind=a.kind,
                    amount_eur=float(a.expense.amount_eur),
                    settled_on=a.expense.settled_on,
                    reason=a.reason,
                )
                for a in expense_report.anomalies
            ],
        ),
        reconcile=ReconcileOut(
            matched=len(recon.matches),
            orphan_payouts=len(recon.orphan_payouts),
            orphan_credits=len(recon.orphan_credits),
            summary=recon.summary(),
        ),
        contracts=ContractsOut(
            vendors=[
                VendorContractOut(
                    vendor=c.vendor,
                    renewal_date=c.renewal_date,
                    deadline_date=c.deadline_date,
                    days_until=c.days_until_deadline,
                    status=c.status,
                    monthly_cost_eur=float(c.monthly_cost_eur),
                )
                for c in vendor_contracts
            ],
            clients=[
                ClientContractOut(
                    client=r.client,
                    next_renewal=r.next_renewal,
                    days_left=r.days_left,
                    status=r.status,
                )
                for r in client_renewals
            ],
        ),
        fiscal=[
            FiscalDeadlineOut(
                kind=d.kind, label=d.label, due_date=d.due_date, days_until=d.days_until
            )
            for d in calendar
        ],
        rgpd=RgpdOut(
            present=rgpd.present,
            should_alert=rgpd.should_alert,
            summary=rgpd.summary,
            treatments=[
                TreatmentOut(
                    nom=t.nom,
                    base_legale=t.base_legale,
                    finalite=t.finalite,
                    donnees=list(t.donnees),
                    review_date=t.review_date,
                    conforme=t.conforme,
                    issues=list(t.issues),
                )
                for t in rgpd.treatments
            ],
        ),
        ai_act=AiActOut(
            present=ai_act.present,
            should_alert=ai_act.should_alert,
            summary=ai_act.summary,
            counts=ai_act.counts,
            systems=[AiActSystemOut(nom=s.nom, role=s.role, risk=s.risk) for s in ai_act.systems],
        ),
        incidents=[
            IncidentOut(
                slug=i.slug,
                title=i.title,
                date=i.date,
                category=i.category,
                severity=i.severity,
                status=i.status,
            )
            for i in incident_items
        ],
        docs=[DocOut(name=d.name, kind=d.kind, has_pdf=d.has_pdf) for d in doc_items],
        uploads=upload_items,
        contexts=context_ids,
        compliance_blocking=blocking,
        compliance_reason=reason,
        counts=counts,
    )


@router.get("/docs/{name}", response_model=DocContent)
async def get_doc(name: str) -> DocContent:
    """Contenu markdown d'un document généré (preview cockpit)."""
    content = docs.read_doc(name, poles_root=POLES_DIR)
    if content is None:
        raise HTTPException(status_code=404, detail=f"Document introuvable : {name}")
    return DocContent(name=name, content=content)


# =============================================================================
# Routes — mutations
# =============================================================================
@router.post("/ledger/flows", response_model=FlowOut, status_code=status.HTTP_201_CREATED)
async def add_flow(payload: FlowPayload) -> FlowOut:
    """Ajoute une ligne au tableur des flux (idempotent par contenu)."""
    # Garde déterministe : inf/NaN passent la validation float (json accepte ces
    # tokens), donc on les rejette ici en 422 avec un détail string — sinon la
    # valeur non-finie remonterait en 500 (quantize / comparaison / sérialisation).
    if not math.isfinite(payload.amount_eur):
        raise HTTPException(status_code=422, detail="Montant invalide (inf/NaN).")
    try:
        amount = Decimal(str(payload.amount_eur))
    except (InvalidOperation, ValueError) as exc:
        raise HTTPException(status_code=422, detail="Montant invalide") from exc
    if amount <= 0:
        raise HTTPException(status_code=422, detail="Le montant doit être positif (> 0).")
    direction: ledger.FlowDirection = "out" if payload.direction == "out" else "in"
    flow = ledger.add_flow(
        flow_date=payload.flow_date,
        label=payload.label.strip() or "(sans libellé)",
        category=payload.category.strip() or "autre",
        direction=direction,
        amount_eur=amount,
        poles_root=POLES_DIR,
    )
    # Solde recalculé en contexte complet (la ligne n'est pas forcément la dernière).
    flows = ledger.load_flows(poles_root=POLES_DIR)
    balance = Decimal("0.00")
    for fl in flows:
        balance += fl.signed_eur
        if fl.id == flow.id:
            break
    return FlowOut(
        id=flow.id,
        flow_date=flow.flow_date,
        label=flow.label,
        category=flow.category,
        direction=flow.direction,
        amount_eur=float(flow.amount_eur),
        balance_eur=float(balance),
    )


@router.delete("/ledger/flows/{flow_id}")
async def delete_flow(flow_id: str) -> dict[str, bool]:
    """Supprime une ligne du tableur. 404 si absente."""
    if not ledger.delete_flow(flow_id, poles_root=POLES_DIR):
        raise HTTPException(status_code=404, detail=f"Ligne introuvable : {flow_id}")
    return {"deleted": True}


@router.post("/docs/generate", response_model=DocGenResult)
async def generate_doc(payload: GenerateDocPayload) -> DocGenResult:
    """Génère un document (CA3 / devis / contrat).

    Garde-fou « Python tranche » : la génération d'un **devis / contrat** (onboarding
    d'un nouveau client = nouveau traitement PII) est refusée (409) tant que la
    conformité RGPD / AI Act est bloquante.
    """
    kind = payload.kind
    path: Path | None
    if kind == "ca3":
        path = docs.generate_ca3(poles_root=POLES_DIR)
    elif kind in ("proposal", "contract"):
        if compliance.compliance_blocking(poles_root=POLES_DIR):
            raise HTTPException(
                status_code=409,
                detail=(
                    "Onboarding gelé (conformité RGPD/AI Act non garantie) — "
                    f"{compliance.blocking_reason(poles_root=POLES_DIR)}"
                ),
            )
        if not payload.deal_id:
            raise HTTPException(status_code=422, detail="deal_id requis pour un devis/contrat.")
        gen = docs.generate_proposal if kind == "proposal" else docs.generate_contract
        path = gen(payload.deal_id, poles_root=POLES_DIR)
        if path is None:
            raise HTTPException(
                status_code=404, detail=f"Contexte devis/contrat introuvable : {payload.deal_id}"
            )
    else:
        raise HTTPException(status_code=422, detail=f"Type de doc inconnu : {kind}")
    return DocGenResult(name=path.name, kind=kind, has_pdf=path.with_suffix(".pdf").exists())


@router.post("/docs/upload", response_model=DocGenResult, status_code=status.HTTP_201_CREATED)
async def upload_doc(payload: UploadPayload) -> DocGenResult:
    """Enregistre un document à remplir (uploadé) dans ``docs/uploads/``."""
    if not payload.filename.strip():
        raise HTTPException(status_code=422, detail="Nom de fichier requis.")
    path = docs.save_upload(payload.filename, payload.content, poles_root=POLES_DIR)
    return DocGenResult(name=path.name, kind="upload", has_pdf=False)


@router.post("/invoices/{invoice_id}/dunning", response_model=DunningResult)
async def draft_dunning(invoice_id: str) -> DunningResult:
    """Drafte la relance d'une facture impayée (mode shadow — aucun envoi)."""
    invoices = {i.id: i for i in billing.load_invoices(poles_root=POLES_DIR)}
    if invoice_id not in invoices:
        raise HTTPException(status_code=404, detail=f"Facture introuvable : {invoice_id}")
    path = billing.draft_dunning(invoice_id, poles_root=POLES_DIR)
    if path is None:
        raise HTTPException(
            status_code=409, detail="Facture pas en retard (rien à relancer pour l'instant)."
        )
    return DunningResult(invoice_id=invoice_id, status="drafted", draft_path=path.name)


@router.post("/export/accounting", response_model=ExportResult)
async def export_accounting() -> ExportResult:
    """Produit l'export comptable CSV depuis le tableur des flux."""
    path = accounting.export_accounting(poles_root=POLES_DIR)
    return ExportResult(path=path.name, csv=path.read_text(encoding="utf-8"))


__all__ = ["router"]
