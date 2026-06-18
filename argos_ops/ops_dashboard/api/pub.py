"""Endpoints cockpit du pôle **Pub** (archi v2, S3).

Sert au shell ``poles.html`` tout ce dont l'onglet Pub a besoin, 100 % fichiers /
local-first (D-017) :

- ``GET    /api/poles/pub/overview``                — dashboard campagnes, jauge
  budget + breaker, recos chiffrées, créas, plateformes, compteurs.
- ``POST   /api/poles/pub/creatives``               — crée une créa (status=draft).
- ``POST   /api/poles/pub/creatives/{id}/validate`` — passe en ``validated``.
- ``POST   /api/poles/pub/creatives/{id}/reject``   — passe en ``rejected``.
- ``POST   /api/poles/pub/creatives/{id}/golive``   — passe en ``live`` (shadow ;
  bloqué si le breaker est armé).
- ``PUT    /api/poles/pub/budget``                  — règle l'enveloppe journalière.
- ``POST   /api/poles/pub/breaker/reset``           — désarme ``ad_spend_runaway``.
- ``POST   /api/poles/pub/recommendations/apply``   — applique une reco (shadow ;
  les augmentatrices de dépense sont bloquées si le breaker est armé).
- ``POST   /api/poles/pub/simulate``                — simulateur de budget.

La **jauge** est recalculée à chaud depuis le dernier CSV (photo du moment) ; le
**breaker** est l'état persistant (latch) lu/écrit dans ``budget.yaml``. Les
routes de lecture ne mutent jamais l'état (seul le script ``ads_optimizer`` arme
le breaker). ``POLES_DIR`` est un global de module → patchable en test.
"""

from __future__ import annotations

import dataclasses
from datetime import datetime

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from argos_ops.poles.config import POLES_DIR
from argos_ops.poles.pub import applied as applied_mod
from argos_ops.poles.pub import budget as budget_mod
from argos_ops.poles.pub import creatives as creatives_mod
from argos_ops.poles.pub import optimizer as optimizer_mod
from argos_ops.poles.pub.creatives import slugify
from argos_ops.poles.pub.optimizer import SPEND_INCREASING, AdRecommendation, CampaignRow
from argos_ops.poles.pub.platforms import PLATFORMS, get_platform

router = APIRouter(prefix="/api/poles/pub", tags=["poles", "pub"])

_CPA_TARGET_EUR = 80.0


# =============================================================================
# Schemas
# =============================================================================
class PlatformOut(BaseModel):
    id: str
    label: str
    creative_skill: str
    headline_max: int
    headline_count: int
    primary_max: int
    keyword_targeted: bool


class BudgetOut(BaseModel):
    daily_budget_eur: float
    runaway_multiplier: float
    window_days: int
    spent_per_day_eur: float
    spent_window_eur: float
    utilization: float
    runaway_threshold_eur: float
    over_threshold: bool
    by_platform: dict[str, float]
    breaker_tripped: bool
    breaker_reason: str | None
    breaker_tripped_at: datetime | None


class RecommendationOut(BaseModel):
    id: str
    platform: str
    campaign: str
    action: str
    severity: str
    eur_delta_week: float
    rationale: str
    metrics: dict[str, float]
    spend_increasing: bool
    applied: bool
    blocked_by_breaker: bool


class CampaignOut(BaseModel):
    platform: str
    campaign: str
    impressions: int
    clicks: int
    cost_eur: float
    conversions: int
    ctr: float
    cpc: float
    cpa: float
    conv_rate: float


class VariantOut(BaseModel):
    label: str
    angle: str
    headline: str
    primary_text: str
    description: str
    headline_len: int
    headline_ok: bool
    primary_len: int
    primary_ok: bool


class CreativeOut(BaseModel):
    id: str
    platform: str
    title: str
    status: str
    objective: str | None
    persona: str | None
    source: str | None
    brief: str
    created_at: datetime
    updated_at: datetime
    variants: list[VariantOut]


class PubCounts(BaseModel):
    creatives: int
    draft: int
    validated: int
    live: int
    rejected: int
    recommendations: int
    critical: int
    applied: int
    potential_savings_week_eur: float
    potential_scale_week_eur: float


class PubOverview(BaseModel):
    pole: str
    generated_at: datetime
    platforms: list[PlatformOut]
    budget: BudgetOut
    recommendations: list[RecommendationOut]
    campaigns: list[CampaignOut]
    creatives: list[CreativeOut]
    counts: PubCounts


# =============================================================================
# Payloads
# =============================================================================
class VariantPayload(BaseModel):
    label: str
    angle: str = ""
    headline: str
    primary_text: str = ""
    description: str = ""


class CreativeCreatePayload(BaseModel):
    platform: str
    title: str
    variants: list[VariantPayload] = []
    objective: str | None = None
    persona: str | None = None
    brief: str = ""
    source: str | None = None


class BudgetPayload(BaseModel):
    daily_budget_eur: float


class ApplyPayload(BaseModel):
    platform: str
    campaign: str
    action: str
    eur_delta_week: float = 0.0
    rationale: str = ""


class SimulatePayload(BaseModel):
    per_platform_daily: dict[str, float]
    daily_budget_eur: float | None = None


class AppliedOut(BaseModel):
    id: str
    platform: str
    campaign: str
    action: str
    eur_delta_week: float
    rationale: str
    mode: str
    applied_at: datetime


class SimAllocationOut(BaseModel):
    platform: str
    daily_eur: float
    cpa_eur: float
    weekly_spend_eur: float
    weekly_leads: float


class SimulationOut(BaseModel):
    total_daily_eur: float
    weekly_spend_eur: float
    weekly_leads: float
    blended_cpa_eur: float
    exceeds_budget: bool
    would_trip: bool
    allocations: list[SimAllocationOut]


# =============================================================================
# Helpers
# =============================================================================
def _current_budget() -> budget_mod.Budget:
    """Budget *live* : config + latch breaker de ``budget.yaml``, dépense recalculée
    depuis le dernier CSV (photo du moment). Ne persiste rien (lecture seule)."""
    state = budget_mod.load_budget(poles_root=POLES_DIR)
    rows = optimizer_mod.load_latest_campaigns(poles_root=POLES_DIR)
    if not rows:
        return state
    spend = optimizer_mod.spend_by_platform(rows)
    window = max(1, state.window_days)
    spent_window = sum(spend.values())
    return dataclasses.replace(
        state,
        by_platform=spend,
        spent_window_eur=spent_window,
        spent_per_day_eur=spent_window / window,
    )


def _budget_out(b: budget_mod.Budget) -> BudgetOut:
    return BudgetOut(
        daily_budget_eur=b.daily_budget_eur,
        runaway_multiplier=b.runaway_multiplier,
        window_days=b.window_days,
        spent_per_day_eur=round(b.spent_per_day_eur, 2),
        spent_window_eur=round(b.spent_window_eur, 2),
        utilization=round(b.utilization, 4),
        runaway_threshold_eur=round(b.runaway_threshold_eur, 2),
        over_threshold=b.over_threshold,
        by_platform={k: round(v, 2) for k, v in b.by_platform.items()},
        breaker_tripped=b.breaker_tripped,
        breaker_reason=b.breaker_reason,
        breaker_tripped_at=b.breaker_tripped_at,
    )


def _reco_out(
    reco: AdRecommendation, *, applied_ids: set[str], breaker_tripped: bool
) -> RecommendationOut:
    spend_increasing = reco.action in SPEND_INCREASING
    return RecommendationOut(
        id=reco.id,
        platform=reco.platform,
        campaign=reco.campaign,
        action=reco.action,
        severity=reco.severity,
        eur_delta_week=round(reco.eur_delta_week, 2),
        rationale=reco.rationale,
        metrics=reco.metrics,
        spend_increasing=spend_increasing,
        applied=reco.id in applied_ids,
        blocked_by_breaker=breaker_tripped and spend_increasing,
    )


def _campaign_out(row: CampaignRow) -> CampaignOut:
    return CampaignOut(
        platform=row.platform,
        campaign=row.campaign,
        impressions=row.impressions,
        clicks=row.clicks,
        cost_eur=round(row.cost_eur, 2),
        conversions=row.conversions,
        ctr=round(row.ctr, 4),
        cpc=round(row.cpc, 2),
        cpa=round(row.cpa, 2),
        conv_rate=round(row.conv_rate, 4),
    )


def _variant_out(v: creatives_mod.Variant, platform_id: str) -> VariantOut:
    plat = get_platform(platform_id)
    return VariantOut(
        label=v.label,
        angle=v.angle,
        headline=v.headline,
        primary_text=v.primary_text,
        description=v.description,
        headline_len=len(v.headline),
        headline_ok=plat.headline_ok(v.headline) if plat else True,
        primary_len=len(v.primary_text),
        primary_ok=plat.primary_ok(v.primary_text) if plat else True,
    )


def _creative_out(c: creatives_mod.Creative) -> CreativeOut:
    return CreativeOut(
        id=c.id,
        platform=c.platform,
        title=c.title,
        status=c.status,
        objective=c.objective,
        persona=c.persona,
        source=c.source,
        brief=c.brief,
        created_at=c.created_at,
        updated_at=c.updated_at,
        variants=[_variant_out(v, c.platform) for v in c.variants],
    )


# =============================================================================
# Routes — lecture
# =============================================================================
@router.get("/overview", response_model=PubOverview)
async def get_overview() -> PubOverview:
    """Tout ce dont l'onglet Pub a besoin en un seul fetch."""
    rows_by_platform = optimizer_mod.load_latest_campaigns(poles_root=POLES_DIR)
    state = _current_budget()
    recos = optimizer_mod.recommend(
        rows_by_platform, cpa_target_eur=_CPA_TARGET_EUR, window_days=state.window_days
    )
    applied_ids = applied_mod.applied_ids(poles_root=POLES_DIR)
    creatives = creatives_mod.load_creatives(poles_root=POLES_DIR)

    reco_outs = [
        _reco_out(r, applied_ids=applied_ids, breaker_tripped=state.breaker_tripped) for r in recos
    ]
    campaigns = [
        _campaign_out(row)
        for platform in sorted(rows_by_platform)
        for row in rows_by_platform[platform]
    ]
    savings = -sum(r.eur_delta_week for r in recos if r.eur_delta_week < 0)
    scale = sum(r.eur_delta_week for r in recos if r.eur_delta_week > 0)

    counts = PubCounts(
        creatives=len(creatives),
        draft=sum(1 for c in creatives if c.status == "draft"),
        validated=sum(1 for c in creatives if c.status == "validated"),
        live=sum(1 for c in creatives if c.status == "live"),
        rejected=sum(1 for c in creatives if c.status == "rejected"),
        recommendations=len(recos),
        critical=sum(1 for r in recos if r.severity == "critical"),
        applied=len(applied_ids),
        potential_savings_week_eur=round(savings, 2),
        potential_scale_week_eur=round(scale, 2),
    )
    return PubOverview(
        pole="pub",
        generated_at=datetime.now(tz=state.updated_at.tzinfo),
        platforms=[
            PlatformOut(
                id=p.id,
                label=p.label,
                creative_skill=p.creative_skill,
                headline_max=p.headline_max,
                headline_count=p.headline_count,
                primary_max=p.primary_max,
                keyword_targeted=p.keyword_targeted,
            )
            for p in PLATFORMS
        ],
        budget=_budget_out(state),
        recommendations=reco_outs,
        campaigns=campaigns,
        creatives=[_creative_out(c) for c in creatives],
        counts=counts,
    )


# =============================================================================
# Routes — créas
# =============================================================================
@router.post("/creatives", response_model=CreativeOut, status_code=status.HTTP_201_CREATED)
async def create_creative(payload: CreativeCreatePayload) -> CreativeOut:
    if get_platform(payload.platform) is None:
        raise HTTPException(status_code=400, detail=f"Plateforme inconnue : {payload.platform}")
    if not payload.title.strip():
        raise HTTPException(status_code=400, detail="Titre vide")
    variants = tuple(
        creatives_mod.Variant(
            label=v.label,
            angle=v.angle,
            headline=v.headline,
            primary_text=v.primary_text,
            description=v.description,
        )
        for v in payload.variants
    )
    creative = creatives_mod.create_creative(
        platform=payload.platform,
        title=payload.title.strip(),
        variants=variants,
        objective=payload.objective,
        persona=payload.persona,
        brief=payload.brief,
        source=payload.source,
        poles_root=POLES_DIR,
    )
    return _creative_out(creative)


def _require_creative(creative_id: str) -> creatives_mod.Creative:
    creative = creatives_mod.load_creative(creative_id, poles_root=POLES_DIR)
    if creative is None:
        raise HTTPException(status_code=404, detail=f"Créa introuvable : {creative_id}")
    return creative


@router.post("/creatives/{creative_id}/validate", response_model=CreativeOut)
async def validate_creative(creative_id: str) -> CreativeOut:
    creative = _require_creative(creative_id)
    if creative.status == "live":
        raise HTTPException(status_code=409, detail="Créa déjà en ligne — immuable")
    updated = creatives_mod.set_status(creative_id, "validated", poles_root=POLES_DIR)
    return _creative_out(_require_creative_obj(updated, creative_id))


@router.post("/creatives/{creative_id}/reject", response_model=CreativeOut)
async def reject_creative(creative_id: str) -> CreativeOut:
    creative = _require_creative(creative_id)
    if creative.status == "live":
        raise HTTPException(status_code=409, detail="Créa en ligne — la retirer avant de rejeter")
    updated = creatives_mod.set_status(creative_id, "rejected", poles_root=POLES_DIR)
    return _creative_out(_require_creative_obj(updated, creative_id))


@router.post("/creatives/{creative_id}/golive", response_model=CreativeOut)
async def golive_creative(creative_id: str) -> CreativeOut:
    """Passe une créa validée en ``live`` (shadow). Bloqué si le breaker est armé."""
    creative = _require_creative(creative_id)
    if creative.status != "validated":
        raise HTTPException(status_code=409, detail="Créa non validée — valider d'abord")
    if budget_mod.load_budget(poles_root=POLES_DIR).breaker_tripped:
        raise HTTPException(
            status_code=409,
            detail="Breaker ad_spend_runaway armé — mise en ligne gelée (reset requis)",
        )
    updated = creatives_mod.set_status(creative_id, "live", poles_root=POLES_DIR)
    return _creative_out(_require_creative_obj(updated, creative_id))


def _require_creative_obj(
    creative: creatives_mod.Creative | None, creative_id: str
) -> creatives_mod.Creative:
    if creative is None:
        raise HTTPException(status_code=404, detail=f"Créa introuvable : {creative_id}")
    return creative


# =============================================================================
# Routes — budget / breaker / recos / simulateur
# =============================================================================
@router.put("/budget", response_model=BudgetOut)
async def put_budget(payload: BudgetPayload) -> BudgetOut:
    if payload.daily_budget_eur < 0:
        raise HTTPException(status_code=400, detail="Budget négatif")
    budget_mod.set_daily_budget(payload.daily_budget_eur, poles_root=POLES_DIR)
    return _budget_out(_current_budget())


@router.post("/breaker/reset", response_model=BudgetOut)
async def reset_breaker() -> BudgetOut:
    budget_mod.reset_breaker(poles_root=POLES_DIR)
    return _budget_out(_current_budget())


@router.post(
    "/recommendations/apply", response_model=AppliedOut, status_code=status.HTTP_201_CREATED
)
async def apply_recommendation(payload: ApplyPayload) -> AppliedOut:
    """Applique une reco en shadow. Une action augmentatrice de dépense est
    refusée (409) tant que le breaker ``ad_spend_runaway`` est armé."""
    if get_platform(payload.platform) is None:
        raise HTTPException(status_code=400, detail=f"Plateforme inconnue : {payload.platform}")
    if (
        payload.action in SPEND_INCREASING
        and budget_mod.load_budget(poles_root=POLES_DIR).breaker_tripped
    ):
        raise HTTPException(
            status_code=409,
            detail=f"Breaker armé — action « {payload.action} » (augmente la dépense) gelée",
        )
    reco_id = f"{payload.platform}-{slugify(payload.campaign)}-{payload.action}"
    record = applied_mod.record_applied(
        reco_id=reco_id,
        platform=payload.platform,
        campaign=payload.campaign,
        action=payload.action,
        eur_delta_week=payload.eur_delta_week,
        rationale=payload.rationale,
        poles_root=POLES_DIR,
    )
    return AppliedOut(
        id=record.id,
        platform=record.platform,
        campaign=record.campaign,
        action=record.action,
        eur_delta_week=record.eur_delta_week,
        rationale=record.rationale,
        mode=record.mode,
        applied_at=record.applied_at,
    )


@router.post("/simulate", response_model=SimulationOut)
async def simulate(payload: SimulatePayload) -> SimulationOut:
    state = budget_mod.load_budget(poles_root=POLES_DIR)
    rows = optimizer_mod.load_latest_campaigns(poles_root=POLES_DIR)
    cpa = optimizer_mod.cpa_by_platform(rows)
    daily_budget = (
        payload.daily_budget_eur if payload.daily_budget_eur is not None else state.daily_budget_eur
    )
    sim = budget_mod.simulate_budget(
        payload.per_platform_daily,
        daily_budget_eur=daily_budget,
        cpa_by_platform=cpa,
        multiplier=state.runaway_multiplier,
        days=state.window_days,
    )
    return SimulationOut(
        total_daily_eur=round(sim.total_daily_eur, 2),
        weekly_spend_eur=round(sim.weekly_spend_eur, 2),
        weekly_leads=round(sim.weekly_leads, 2),
        blended_cpa_eur=round(sim.blended_cpa_eur, 2),
        exceeds_budget=sim.exceeds_budget,
        would_trip=sim.would_trip,
        allocations=[
            SimAllocationOut(
                platform=a.platform,
                daily_eur=round(a.daily_eur, 2),
                cpa_eur=round(a.cpa_eur, 2),
                weekly_spend_eur=round(a.weekly_spend_eur, 2),
                weekly_leads=round(a.weekly_leads, 2),
            )
            for a in sim.allocations
        ],
    )


__all__ = ["router"]
