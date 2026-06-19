"""Endpoints cockpit du pôle **Vente & Relation Client** (archi v2, S4).

Sert au shell ``poles.html`` tout l'onglet Vente, 100 % fichiers / local-first
(D-017) — tout est recalculé à chaud depuis les fichiers ``data/poles/vente/…`` :

- ``GET  /api/poles/vente/overview``             — pipeline (Kanban + risque), inbox
  triée, comptes (santé/churn/upsell), tickets (SLA), leads enrichis, séquences,
  RDV, devis/contrats, conformité Bloctel, compteurs.
- ``POST /api/poles/vente/leads/upload``         — ajoute des leads au CSV inbox.
- ``POST /api/poles/vente/inbox/{id}/draft``     — drafte une réponse (409 si réponse
  humaine exigée — AI Act).
- ``POST /api/poles/vente/meetings/{id}/book``   — drafte la confirmation + iCal.
- ``POST /api/poles/vente/sequences``            — scaffold une séquence outbound
  (409 si lead inéligible ou outbound gelé Bloctel — « Python tranche »).
- ``POST /api/poles/vente/proposals/{id}/draft`` — rend le devis Markdown.

``POLES_DIR`` est un global de module → patchable en test.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from argos_ops.outbound.models import LeadInput
from argos_ops.poles.config import POLES_DIR
from argos_ops.poles.vente import accounts as accounts_mod
from argos_ops.poles.vente import inbox as inbox_mod
from argos_ops.poles.vente import meetings as meetings_mod
from argos_ops.poles.vente import outreach as outreach_mod
from argos_ops.poles.vente import pipeline as pipeline_mod
from argos_ops.poles.vente import proposals as proposals_mod
from argos_ops.poles.vente import support as support_mod
from argos_ops.sales.models import DealStage, DealStalledFlag, MeetingRequest

router = APIRouter(prefix="/api/poles/vente", tags=["poles", "vente"])


# =============================================================================
# Schemas — sortie
# =============================================================================
class DealOut(BaseModel):
    deal_id: str
    company: str
    stage: str
    amount_eur: int
    days_since_activity: int
    risk_score: int
    is_stalled: bool
    reason: str


class MessageOut(BaseModel):
    id: str
    from_name: str
    from_email: str
    subject: str
    category: str
    human_requested: bool
    status: str
    received_at: date


class HealthOut(BaseModel):
    customer_id: str
    score: int
    band: str
    drivers: list[str]


class ChurnOut(BaseModel):
    customer_id: str
    risk_score: int
    urgent: bool
    signals: list[str]


class UpsellOut(BaseModel):
    customer_id: str
    usage_ratio: float
    suggested_plan: str
    reason: str


class TicketOut(BaseModel):
    ticket_id: str
    customer_id: str
    subject: str
    priority: str
    sla_response_hours: int
    sla_breached: bool
    reason: str


class LeadOut(BaseModel):
    slug: str
    full_name: str
    domain: str
    title_hint: str | None
    persona: str
    bant_total: int
    qualified: bool
    best_email: str | None
    eligible: bool
    eligibility_reason: str


class BantBreakdownOut(BaseModel):
    budget: int
    authority: int
    need: int
    timing: int
    total: int


class EmailGuessOut(BaseModel):
    email: str
    pattern: str
    confidence: int


class LeadDetailOut(BaseModel):
    # Tous les champs de ``LeadOut`` (résumé) …
    slug: str
    full_name: str
    domain: str
    title_hint: str | None
    persona: str
    bant_total: int
    qualified: bool
    best_email: str | None
    eligible: bool
    eligibility_reason: str
    # … + les champs structurés de l'enrichissement …
    persona_score: int
    persona_signals: list[str]
    bant: BantBreakdownOut
    email_guesses: list[EmailGuessOut]
    # … + le corps markdown de enriched/<slug>.md ("" si pas encore écrit).
    markdown_body: str


class DraftBodyOut(BaseModel):
    id: str
    body: str
    exists: bool


class TouchOut(BaseModel):
    step: int
    scheduled_date: date
    status: str


class SequenceOut(BaseModel):
    slug: str
    full_name: str
    domain: str
    sequence_status: str
    touches: list[TouchOut]


class MeetingOut(BaseModel):
    request_id: str
    attendee_name: str
    attendee_email: str
    company: str
    starts_at: datetime
    duration_minutes: int
    location: str
    status: str


class ProposalOut(BaseModel):
    deal_id: str
    company: str
    plan: str
    monthly_price_eur: int
    proposal_status: str
    has_proposal: bool
    has_contract: bool


class BloctelOut(BaseModel):
    list_path: str | None
    list_age_days: int | None
    checked: int
    matches: int
    stale: bool
    should_alert: bool
    summary: str


class VenteCounts(BaseModel):
    deals_active: int
    pipeline_value_eur: int
    stalled: int
    inbox_total: int
    inbox_new: int
    leads: int
    qualified_leads: int
    eligible_leads: int
    tickets_open: int
    p0: int
    sla_breached: int
    accounts: int
    health_red: int
    churn_urgent: int
    upsell: int
    meetings_pending: int
    proposals: int
    contracts: int
    outbound_frozen: bool


class VenteOverview(BaseModel):
    pole: str
    generated_at: datetime
    stage_order: list[str]
    pipeline: list[DealOut]
    inbox: list[MessageOut]
    health: list[HealthOut]
    churn: list[ChurnOut]
    upsell: list[UpsellOut]
    tickets: list[TicketOut]
    leads: list[LeadOut]
    sequences: list[SequenceOut]
    meetings: list[MeetingOut]
    proposals: list[ProposalOut]
    bloctel: BloctelOut
    counts: VenteCounts


# =============================================================================
# Schemas — entrée
# =============================================================================
class LeadRow(BaseModel):
    full_name: str
    domain: str
    title_hint: str | None = None
    linkedin_url: str | None = None


class LeadUploadPayload(BaseModel):
    rows: list[LeadRow] = []


class ScaffoldPayload(BaseModel):
    slug: str


class StagePayload(BaseModel):
    stage: str


class DraftBodyPayload(BaseModel):
    body: str


class UploadResult(BaseModel):
    added: int
    skipped: int


class DraftResult(BaseModel):
    id: str
    status: str
    draft_path: str


class ScaffoldResult(BaseModel):
    slug: str
    status: str


class MeetingIcsOut(BaseModel):
    request_id: str
    filename: str
    ics: str


# =============================================================================
# Mappers
# =============================================================================
def _deal_out(flag: DealStalledFlag) -> DealOut:
    return DealOut(
        deal_id=flag.deal.deal_id,
        company=flag.deal.company,
        stage=flag.deal.stage.value,
        amount_eur=flag.deal.amount_eur,
        days_since_activity=flag.days_since_activity,
        risk_score=flag.risk_score,
        is_stalled=flag.is_stalled,
        reason=flag.reason,
    )


def _message_out(m: inbox_mod.InboundMessage) -> MessageOut:
    return MessageOut(
        id=m.id,
        from_name=m.from_name,
        from_email=m.from_email,
        subject=m.subject,
        category=m.category,
        human_requested=m.human_requested,
        status=m.status,
        received_at=m.received_at,
    )


def _lead_out(e: outreach_mod.EnrichedLead) -> LeadOut:
    return LeadOut(
        slug=e.slug,
        full_name=e.full_name,
        domain=e.domain,
        title_hint=e.title_hint,
        persona=e.persona,
        bant_total=e.bant_total,
        qualified=e.qualified,
        best_email=e.best_email,
        eligible=e.eligible,
        eligibility_reason=e.eligibility_reason,
    )


def _lead_detail_out(d: outreach_mod.LeadDetail) -> LeadDetailOut:
    e = d.lead
    return LeadDetailOut(
        slug=e.slug,
        full_name=e.full_name,
        domain=e.domain,
        title_hint=e.title_hint,
        persona=e.persona,
        bant_total=e.bant_total,
        qualified=e.qualified,
        best_email=e.best_email,
        eligible=e.eligible,
        eligibility_reason=e.eligibility_reason,
        persona_score=d.persona_score,
        persona_signals=list(d.persona_signals),
        bant=BantBreakdownOut(
            budget=d.bant.budget,
            authority=d.bant.authority,
            need=d.bant.need,
            timing=d.bant.timing,
            total=d.bant.total,
        ),
        email_guesses=[
            EmailGuessOut(email=g.email, pattern=g.pattern, confidence=g.confidence)
            for g in d.email_guesses
        ],
        markdown_body=d.markdown_body,
    )


def _proposal_out(p: proposals_mod.ProposalEntry) -> ProposalOut:
    return ProposalOut(
        deal_id=p.deal_id,
        company=p.company,
        plan=p.plan,
        monthly_price_eur=p.monthly_price_eur,
        proposal_status=p.proposal_status,
        has_proposal=p.has_proposal,
        has_contract=p.has_contract,
    )


def _meeting_out(r: MeetingRequest) -> MeetingOut:
    return MeetingOut(
        request_id=r.request_id,
        attendee_name=r.attendee_name,
        attendee_email=r.attendee_email,
        company=r.company,
        starts_at=r.starts_at,
        duration_minutes=r.duration_minutes,
        location=r.location,
        status=r.status,
    )


# =============================================================================
# Route — lecture
# =============================================================================
@router.get("/overview", response_model=VenteOverview)
async def get_overview() -> VenteOverview:
    """Tout ce dont l'onglet Vente a besoin en un seul fetch."""
    deals = pipeline_mod.load_deals(poles_root=POLES_DIR)
    flags = pipeline_mod.score_pipeline(deals)
    messages = inbox_mod.load_messages(poles_root=POLES_DIR)
    customers = accounts_mod.load_accounts(poles_root=POLES_DIR)
    health = accounts_mod.score_health(customers)
    churn = accounts_mod.detect_churn(customers)
    upsell = accounts_mod.detect_upsells(customers)
    tickets = support_mod.triage(support_mod.load_support_tickets(poles_root=POLES_DIR))
    enriched = [
        outreach_mod.enrich_view(lead) for lead in outreach_mod.load_leads(poles_root=POLES_DIR)
    ]
    sequences = outreach_mod.load_sequences(poles_root=POLES_DIR)
    meeting_reqs = meetings_mod.load_requests(poles_root=POLES_DIR)
    proposal_entries = proposals_mod.load_entries(poles_root=POLES_DIR)
    bloctel = outreach_mod.build_bloctel_report(poles_root=POLES_DIR)

    counts = VenteCounts(
        deals_active=sum(1 for d in deals if d.stage.value not in ("won", "lost")),
        pipeline_value_eur=pipeline_mod.pipeline_value_eur(deals),
        stalled=len(pipeline_mod.stalled_active(flags)),
        inbox_total=len(messages),
        inbox_new=sum(1 for m in messages if m.status == "new"),
        leads=len(enriched),
        qualified_leads=sum(1 for e in enriched if e.qualified),
        eligible_leads=sum(1 for e in enriched if e.eligible),
        tickets_open=len(tickets),
        p0=sum(1 for t in tickets if t.priority.value == "P0"),
        sla_breached=sum(1 for t in tickets if t.sla_breached),
        accounts=len(customers),
        health_red=sum(1 for h in health if h.band.value == "red"),
        churn_urgent=sum(1 for c in churn if c.risk_score >= accounts_mod.URGENT_CHURN_THRESHOLD),
        upsell=len(upsell),
        meetings_pending=sum(1 for r in meeting_reqs if r.status == "pending"),
        proposals=len(proposal_entries),
        contracts=sum(1 for p in proposal_entries if p.has_contract),
        outbound_frozen=bloctel.should_alert,
    )

    return VenteOverview(
        pole="vente",
        generated_at=datetime.now(UTC),
        stage_order=[s.value for s in pipeline_mod.STAGE_ORDER],
        pipeline=[_deal_out(f) for f in flags],
        inbox=[_message_out(m) for m in messages],
        health=[
            HealthOut(
                customer_id=h.customer_id, score=h.score, band=h.band.value, drivers=h.drivers
            )
            for h in health
        ],
        churn=[
            ChurnOut(
                customer_id=c.customer_id,
                risk_score=c.risk_score,
                urgent=c.risk_score >= accounts_mod.URGENT_CHURN_THRESHOLD,
                signals=c.signals,
            )
            for c in churn
        ],
        upsell=[
            UpsellOut(
                customer_id=u.customer_id,
                usage_ratio=u.usage_ratio,
                suggested_plan=u.suggested_plan.value,
                reason=u.reason,
            )
            for u in upsell
        ],
        tickets=[
            TicketOut(
                ticket_id=t.ticket.ticket_id,
                customer_id=t.ticket.customer_id,
                subject=t.ticket.subject,
                priority=t.priority.value,
                sla_response_hours=t.sla_response_hours,
                sla_breached=t.sla_breached,
                reason=t.reason,
            )
            for t in tickets
        ],
        leads=[_lead_out(e) for e in enriched],
        sequences=[
            SequenceOut(
                slug=s.lead_slug,
                full_name=s.full_name,
                domain=s.domain,
                sequence_status=s.sequence_status,
                touches=[
                    TouchOut(step=int(t.step), scheduled_date=t.scheduled_date, status=t.status)
                    for t in s.touches
                ],
            )
            for s in sequences
        ],
        meetings=[_meeting_out(r) for r in meeting_reqs],
        proposals=[_proposal_out(p) for p in proposal_entries],
        bloctel=BloctelOut(
            list_path=bloctel.list_path,
            list_age_days=bloctel.list_age_days,
            checked=bloctel.checked,
            matches=len(bloctel.matches),
            stale=bloctel.stale,
            should_alert=bloctel.should_alert,
            summary=bloctel.summary,
        ),
        counts=counts,
    )


@router.get("/leads/{slug}", response_model=LeadDetailOut)
async def get_lead_detail(slug: str) -> LeadDetailOut:
    """Fiche enrichie complète d'un lead (résumé + breakdown BANT + signaux +
    guesses email + corps markdown si ``enriched/<slug>.md`` existe).

    404 si le slug est inconnu.
    """
    detail = outreach_mod.build_lead_detail(slug, poles_root=POLES_DIR)
    if detail is None:
        raise HTTPException(status_code=404, detail=f"Lead introuvable : {slug}")
    return _lead_detail_out(detail)


@router.get("/inbox/{message_id}/draft", response_model=DraftBodyOut)
async def get_inbox_draft(message_id: str) -> DraftBodyOut:
    """Renvoie le corps du draft de réponse (celui écrit par le POST draft).

    ``exists=false`` + ``body=""`` si aucun draft n'a encore été écrit. 404 si le
    message lui-même est inconnu.
    """
    if not _message_exists(message_id):
        raise HTTPException(status_code=404, detail=f"Message introuvable : {message_id}")
    body = inbox_mod.read_draft(message_id, poles_root=POLES_DIR)
    return DraftBodyOut(id=message_id, body=body or "", exists=body is not None)


# =============================================================================
# Routes — mutations
# =============================================================================
def _message_exists(message_id: str) -> bool:
    return any(m.id == message_id for m in inbox_mod.load_messages(poles_root=POLES_DIR))


@router.post("/leads/upload", response_model=UploadResult, status_code=status.HTTP_201_CREATED)
async def upload_leads(payload: LeadUploadPayload) -> UploadResult:
    """Ajoute des leads au CSV inbox (dédup + validation domaine)."""
    leads = [
        LeadInput(
            full_name=r.full_name,
            domain=r.domain,
            title_hint=r.title_hint,
            linkedin_url=r.linkedin_url,
        )
        for r in payload.rows
    ]
    added, skipped = outreach_mod.append_leads(leads, poles_root=POLES_DIR)
    return UploadResult(added=len(added), skipped=skipped)


@router.post("/inbox/{message_id}/draft", response_model=DraftResult)
async def draft_inbox_reply(message_id: str) -> DraftResult:
    """Drafte une réponse. 409 si une réponse humaine est exigée (AI Act)."""
    try:
        path = inbox_mod.draft_reply(message_id, poles_root=POLES_DIR)
    except inbox_mod.HumanResponseRequiredError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if path is None:
        raise HTTPException(status_code=404, detail=f"Message introuvable : {message_id}")
    return DraftResult(id=message_id, status="drafted", draft_path=str(path.name))


@router.put("/inbox/{message_id}/draft", response_model=DraftBodyOut)
async def save_inbox_draft(message_id: str, payload: DraftBodyPayload) -> DraftBodyOut:
    """Sauvegarde le corps édité du draft de réponse. 404 si le message est inconnu.

    Renvoie le draft relu (``exists=true``).
    """
    if not _message_exists(message_id):
        raise HTTPException(status_code=404, detail=f"Message introuvable : {message_id}")
    inbox_mod.save_draft(message_id, payload.body, poles_root=POLES_DIR)
    body = inbox_mod.read_draft(message_id, poles_root=POLES_DIR)
    return DraftBodyOut(id=message_id, body=body or "", exists=True)


@router.patch("/deals/{deal_id}/stage", response_model=DealOut)
async def move_deal_stage(deal_id: str, payload: StagePayload) -> DealOut:
    """Déplace un deal vers un nouveau stade (drag-drop Kanban).

    422 si le stade n'appartient pas à ``STAGE_ORDER``, 404 si le deal est
    inconnu. Renvoie le ``DealOut`` re-scoré après l'écriture.
    """
    try:
        stage = DealStage(payload.stage)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"Stade inconnu : {payload.stage}") from exc
    if stage not in pipeline_mod.STAGE_ORDER:  # pragma: no cover — défensif (enum ⊆ STAGE_ORDER)
        raise HTTPException(status_code=422, detail=f"Stade hors pipe : {payload.stage}")
    try:
        pipeline_mod.set_deal_stage(deal_id, stage, poles_root=POLES_DIR)
    except pipeline_mod.DealNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Deal introuvable : {deal_id}") from exc
    flags = pipeline_mod.score_pipeline(pipeline_mod.load_deals(poles_root=POLES_DIR))
    flag = next(f for f in flags if f.deal.deal_id == deal_id)
    return _deal_out(flag)


@router.post("/meetings/{request_id}/book", response_model=MeetingOut)
async def book_meeting(request_id: str) -> MeetingOut:
    """Drafte la confirmation + l'invitation iCal d'un RDV."""
    path = meetings_mod.book_meeting(request_id, poles_root=POLES_DIR)
    if path is None:
        raise HTTPException(status_code=404, detail=f"Demande de RDV introuvable : {request_id}")
    req = next(
        (r for r in meetings_mod.load_requests(poles_root=POLES_DIR) if r.request_id == request_id),
        None,
    )
    if req is None:  # pragma: no cover — défensif
        raise HTTPException(status_code=404, detail=f"Demande de RDV introuvable : {request_id}")
    return _meeting_out(req)


@router.get("/meetings/{request_id}/ics", response_model=MeetingIcsOut)
async def get_meeting_ics(request_id: str) -> MeetingIcsOut:
    """Renvoie le texte iCalendar d'un RDV (relu du draft ou régénéré à la volée).

    404 si la demande de RDV est inconnue.
    """
    ics = meetings_mod.read_ics(request_id, poles_root=POLES_DIR)
    if ics is None:
        raise HTTPException(status_code=404, detail=f"Demande de RDV introuvable : {request_id}")
    return MeetingIcsOut(
        request_id=request_id,
        filename=meetings_mod.ics_filename(request_id),
        ics=ics,
    )


@router.post("/sequences", response_model=ScaffoldResult, status_code=status.HTTP_201_CREATED)
async def scaffold_sequence(payload: ScaffoldPayload) -> ScaffoldResult:
    """Scaffold une séquence outbound pour un lead éligible.

    Garde-fou « Python tranche » : refus (409) si le lead est inéligible (email
    perso / BANT < 40) ou si l'outbound est gelé par la conformité Bloctel.
    """
    leads = outreach_mod.load_leads(poles_root=POLES_DIR)
    match = next(
        ((lead, e) for lead in leads if (e := outreach_mod.enrich_view(lead)).slug == payload.slug),
        None,
    )
    if match is None:
        raise HTTPException(status_code=404, detail=f"Lead introuvable : {payload.slug}")
    lead, enriched = match
    if outreach_mod.outbound_frozen(poles_root=POLES_DIR):
        raise HTTPException(
            status_code=409, detail="Outbound gelé (conformité Bloctel) — séquence refusée."
        )
    if not enriched.eligible:
        raise HTTPException(
            status_code=409, detail=f"Lead inéligible : {enriched.eligibility_reason}"
        )
    outreach_mod.scaffold_for_lead(lead, poles_root=POLES_DIR)
    return ScaffoldResult(slug=payload.slug, status="scaffolded")


@router.post("/proposals/{deal_id}/draft", response_model=ProposalOut)
async def draft_proposal(deal_id: str) -> ProposalOut:
    """Rend le devis Markdown d'un deal (idempotent)."""
    path = proposals_mod.render_proposal_file(deal_id, poles_root=POLES_DIR)
    if path is None:
        raise HTTPException(status_code=404, detail=f"Deal sans contexte devis : {deal_id}")
    entry = next(
        (p for p in proposals_mod.load_entries(poles_root=POLES_DIR) if p.deal_id == deal_id), None
    )
    if entry is None:  # pragma: no cover — défensif
        raise HTTPException(status_code=404, detail=f"Deal introuvable : {deal_id}")
    return _proposal_out(entry)


__all__ = ["router"]
