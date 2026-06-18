"""Endpoints cockpit du pôle **Marketing** (archi v2, S2).

Sert au shell ``poles.html`` tout ce dont l'onglet Marketing a besoin, 100 %
fichiers / local-first (D-017) :

- ``GET    /api/poles/marketing/overview``            — recommandations éditoriales
  (synthèse Veille + propre), file de drafts, canaux, engagement, KB, charte.
- ``POST   /api/poles/marketing/drafts``              — crée un draft (status=draft).
- ``PUT    /api/poles/marketing/drafts/{id}``         — édite titre / corps (inline).
- ``POST   /api/poles/marketing/drafts/{id}/validate``— passe en ``validated``.
- ``POST   /api/poles/marketing/drafts/{id}/reject``  — passe en ``rejected``.
- ``POST   /api/poles/marketing/drafts/{id}/schedule``— (dé)planifie (calendrier).
- ``PUT    /api/poles/marketing/kb/{slug}``           — upsert d'une fiche KB.
- ``DELETE /api/poles/marketing/kb/{slug}``           — supprime une fiche KB.
- ``PUT    /api/poles/marketing/charter``             — enregistre la charte/ton.

Les mutations écrivent dans la donnée **du pôle Marketing** uniquement (pas de
cross-pôle ; la Veille est lue en read-only). ``POLES_DIR`` / ``ENGAGEMENT_PATH``
sont des globals de module → patchables en test (mémoire hermétique).
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from argos_ops.marketing.analytics import DEFAULT_ENGAGEMENT, load_engagement_window
from argos_ops.poles.config import POLES_DIR
from argos_ops.poles.marketing import charter as charter_mod
from argos_ops.poles.marketing import drafts as drafts_mod
from argos_ops.poles.marketing import kb as kb_mod
from argos_ops.poles.marketing.agent import MarketingAgent
from argos_ops.poles.marketing.channels import CHANNELS, get_channel
from argos_ops.poles.marketing.drafts import slugify
from argos_ops.poles.marketing.editorial import Recommendation, plan_editorial
from argos_ops.poles.marketing.scripts.social_analytics import aggregate_engagement
from argos_ops.poles.memory import MemoryRecord

router = APIRouter(prefix="/api/poles/marketing", tags=["poles", "marketing"])

# Globals de module (patchables en test pour une mémoire hermétique).
ENGAGEMENT_PATH = DEFAULT_ENGAGEMENT
_ENGAGEMENT_WINDOW_DAYS = 7


# =============================================================================
# Schemas
# =============================================================================
class ChannelOut(BaseModel):
    id: str
    label: str
    writer_skill: str
    max_chars: int
    min_chars: int
    social: bool


class RecommendationOut(BaseModel):
    kind: str
    topic: str
    angle: str
    severity: str
    channels: list[str]
    rationale: str
    record_ids: list[str]
    count: int


class DraftOut(BaseModel):
    id: str
    channel: str
    title: str
    body: str
    status: str
    writer: str | None
    source: str | None
    scheduled_for: datetime | None
    created_at: datetime
    updated_at: datetime
    length: int
    max_chars: int
    length_ok: bool


class EngagementOut(BaseModel):
    channel: str
    posts: int
    impressions: int
    engagements: int
    clicks: int
    ctr: float
    engagement_rate: float
    weak: bool


class KBEntryOut(BaseModel):
    slug: str
    title: str
    body: str
    tags: list[str]
    updated_at: datetime


class CharterOut(BaseModel):
    tagline: str
    domain: str
    voice: str
    principles: list[str]
    avoid: list[str]
    banned_terms: list[str]
    ai_disclosure: str


class MarketingCounts(BaseModel):
    drafts: int
    pending: int
    validated: int
    scheduled: int
    published: int
    recommendations: int
    critical: int


class MarketingOverview(BaseModel):
    pole: str
    generated_at: datetime
    channels: list[ChannelOut]
    recommendations: list[RecommendationOut]
    drafts: list[DraftOut]
    engagement: list[EngagementOut]
    kb: list[KBEntryOut]
    charter: CharterOut
    counts: MarketingCounts


# =============================================================================
# Payloads
# =============================================================================
class DraftCreatePayload(BaseModel):
    channel: str
    title: str
    body: str
    writer: str | None = None
    source: str | None = None


class DraftEditPayload(BaseModel):
    title: str | None = None
    body: str | None = None


class SchedulePayload(BaseModel):
    scheduled_for: datetime | None = None


class KBUpsertPayload(BaseModel):
    title: str
    body: str
    tags: list[str] = []


class CharterPayload(BaseModel):
    tagline: str
    domain: str
    voice: str
    principles: list[str]
    avoid: list[str]
    banned_terms: list[str]
    ai_disclosure: str


# =============================================================================
# Mappers
# =============================================================================
def _draft_out(draft: drafts_mod.Draft) -> DraftOut:
    channel = get_channel(draft.channel)
    max_chars = channel.max_chars if channel else 0
    return DraftOut(
        id=draft.id,
        channel=draft.channel,
        title=draft.title,
        body=draft.body,
        status=draft.status,
        writer=draft.writer,
        source=draft.source,
        scheduled_for=draft.scheduled_for,
        created_at=draft.created_at,
        updated_at=draft.updated_at,
        length=len(draft.body),
        max_chars=max_chars,
        length_ok=channel.length_ok(draft.body) if channel else True,
    )


def _reco_out(rec: Recommendation) -> RecommendationOut:
    return RecommendationOut(
        kind=rec.kind,
        topic=rec.topic,
        angle=rec.angle,
        severity=rec.severity,
        channels=list(rec.channels),
        rationale=rec.rationale,
        record_ids=list(rec.record_ids),
        count=rec.count,
    )


def _kb_out(entry: kb_mod.KBEntry) -> KBEntryOut:
    return KBEntryOut(
        slug=entry.slug,
        title=entry.title,
        body=entry.body,
        tags=list(entry.tags),
        updated_at=entry.updated_at,
    )


def _charter_out(c: charter_mod.Charter) -> CharterOut:
    return CharterOut(
        tagline=c.tagline,
        domain=c.domain,
        voice=c.voice,
        principles=list(c.principles),
        avoid=list(c.avoid),
        banned_terms=list(c.banned_terms),
        ai_disclosure=c.ai_disclosure,
    )


async def _visible_records() -> list[MemoryRecord]:
    """Mémoire visible par l'agent = propre + cross-pôle déclaré (``pole.yaml``).

    On délègue au socle (``MarketingAgent.load_context``) plutôt que de hardcoder
    « veille » : l'overview du cockpit reste ainsi le miroir exact de ce que voit
    l'agent (respecte ``reads_cross_pole`` et le wildcard, source unique).
    """
    context = await MarketingAgent(poles_root=POLES_DIR).load_context()
    return context.all_records()


def _engagement() -> list[EngagementOut]:
    metrics = load_engagement_window(days=_ENGAGEMENT_WINDOW_DAYS, path=ENGAGEMENT_PATH)
    out: list[EngagementOut] = []
    for channel, agg in sorted(aggregate_engagement(metrics).items()):
        out.append(
            EngagementOut(
                channel=channel,
                posts=agg.posts,
                impressions=agg.impressions,
                engagements=agg.engagements,
                clicks=agg.clicks,
                ctr=agg.ctr,
                engagement_rate=agg.engagement_rate,
                weak=agg.is_weak,
            )
        )
    return out


# =============================================================================
# Routes
# =============================================================================
@router.get("/overview", response_model=MarketingOverview)
async def get_overview() -> MarketingOverview:
    """Tout ce dont l'onglet Marketing a besoin en un seul fetch."""
    records = await _visible_records()
    recommendations = plan_editorial(records)
    drafts = drafts_mod.load_drafts(poles_root=POLES_DIR)
    kb_entries = kb_mod.load_kb(poles_root=POLES_DIR)
    charter = charter_mod.load_charter(poles_root=POLES_DIR)

    counts = MarketingCounts(
        drafts=len(drafts),
        pending=sum(1 for d in drafts if d.status == "draft"),
        validated=sum(1 for d in drafts if d.status == "validated"),
        scheduled=sum(1 for d in drafts if d.status == "validated" and d.scheduled_for is not None),
        published=sum(1 for d in drafts if d.status == "published"),
        recommendations=len(recommendations),
        critical=sum(1 for r in recommendations if r.severity == "critical"),
    )
    return MarketingOverview(
        pole="marketing",
        generated_at=datetime.now(UTC),
        channels=[
            ChannelOut(
                id=c.id,
                label=c.label,
                writer_skill=c.writer_skill,
                max_chars=c.max_chars,
                min_chars=c.min_chars,
                social=c.social,
            )
            for c in CHANNELS
        ],
        recommendations=[_reco_out(r) for r in recommendations],
        drafts=[_draft_out(d) for d in drafts],
        engagement=_engagement(),
        kb=[_kb_out(e) for e in kb_entries],
        charter=_charter_out(charter),
        counts=counts,
    )


@router.post("/drafts", response_model=DraftOut, status_code=status.HTTP_201_CREATED)
async def create_draft(payload: DraftCreatePayload) -> DraftOut:
    if get_channel(payload.channel) is None:
        raise HTTPException(status_code=400, detail=f"Canal inconnu : {payload.channel}")
    if not payload.title.strip():
        raise HTTPException(status_code=400, detail="Titre vide")
    draft = drafts_mod.create_draft(
        channel=payload.channel,
        title=payload.title.strip(),
        body=payload.body,
        writer=payload.writer,
        source=payload.source,
        poles_root=POLES_DIR,
    )
    return _draft_out(draft)


def _require_draft(draft: drafts_mod.Draft | None, draft_id: str) -> drafts_mod.Draft:
    if draft is None:
        raise HTTPException(status_code=404, detail=f"Draft introuvable : {draft_id}")
    return draft


def _require_mutable(draft_id: str) -> drafts_mod.Draft:
    """404 si le draft n'existe pas, 409 s'il est ``published`` (cycle terminal).

    Défend l'invariant draft→validated→published côté serveur : un post déjà
    publié ne doit pas pouvoir être ré-édité / re-validé / re-planifié (sinon
    double-post le jour où les connecteurs passent en live).
    """
    draft = _require_draft(drafts_mod.load_draft(draft_id, poles_root=POLES_DIR), draft_id)
    if draft.status == "published":
        raise HTTPException(status_code=409, detail="Draft publié — immuable")
    return draft


@router.put("/drafts/{draft_id}", response_model=DraftOut)
async def edit_draft(draft_id: str, payload: DraftEditPayload) -> DraftOut:
    _require_mutable(draft_id)
    draft = drafts_mod.edit_draft(
        draft_id, title=payload.title, body=payload.body, poles_root=POLES_DIR
    )
    return _draft_out(_require_draft(draft, draft_id))


@router.post("/drafts/{draft_id}/validate", response_model=DraftOut)
async def validate_draft(draft_id: str) -> DraftOut:
    _require_mutable(draft_id)
    draft = drafts_mod.set_status(draft_id, "validated", poles_root=POLES_DIR)
    return _draft_out(_require_draft(draft, draft_id))


@router.post("/drafts/{draft_id}/reject", response_model=DraftOut)
async def reject_draft(draft_id: str) -> DraftOut:
    _require_mutable(draft_id)
    draft = drafts_mod.set_status(draft_id, "rejected", poles_root=POLES_DIR)
    return _draft_out(_require_draft(draft, draft_id))


@router.post("/drafts/{draft_id}/schedule", response_model=DraftOut)
async def schedule_draft(draft_id: str, payload: SchedulePayload) -> DraftOut:
    _require_mutable(draft_id)
    draft = drafts_mod.schedule_draft(draft_id, payload.scheduled_for, poles_root=POLES_DIR)
    return _draft_out(_require_draft(draft, draft_id))


@router.put("/kb/{slug}", response_model=KBEntryOut)
async def upsert_kb(slug: str, payload: KBUpsertPayload) -> KBEntryOut:
    if not payload.title.strip():
        raise HTTPException(status_code=400, detail="Titre vide")
    # Re-normalise le slug reçu (défense en profondeur : nom de fichier canonique
    # quel que soit le client, pas de segment exotique dans data/.../kb/).
    entry = kb_mod.upsert_kb_entry(
        slug=slugify(slug),
        title=payload.title.strip(),
        body=payload.body,
        tags=tuple(payload.tags),
        poles_root=POLES_DIR,
    )
    return _kb_out(entry)


@router.delete("/kb/{slug}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_kb(slug: str) -> None:
    if not kb_mod.delete_kb_entry(slugify(slug), poles_root=POLES_DIR):
        raise HTTPException(status_code=404, detail=f"Fiche KB introuvable : {slug}")


@router.put("/charter", response_model=CharterOut)
async def put_charter(payload: CharterPayload) -> CharterOut:
    charter = charter_mod.Charter(
        tagline=payload.tagline,
        domain=payload.domain,
        voice=payload.voice,
        principles=tuple(payload.principles),
        avoid=tuple(payload.avoid),
        banned_terms=tuple(payload.banned_terms),
        ai_disclosure=payload.ai_disclosure,
    )
    charter_mod.save_charter(charter, poles_root=POLES_DIR)
    return _charter_out(charter)


__all__ = ["router"]
