"""Endpoints cockpit du pôle **Mémoire** (archi v2, S7).

Sert au shell ``poles.html`` tout l'onglet Mémoire, 100 % fichiers / local-first
(D-017) — tout est recalculé à chaud depuis la mémoire des pôles +
``data/poles/memoire/{policy,history}.yaml`` :

- ``GET  /api/poles/memoire/overview``   — policy + stats mémoire par pôle + audit
  câblage + historique récent + compteurs.
- ``GET  /api/poles/memoire/browse``     — navigateur mémoire (filtre pôle / script /
  texte / important) + facettes.
- ``GET  /api/poles/memoire/plan``       — plan de curation d'un pôle (PREVIEW :
  candidats à la suppression + faits protégés).
- ``POST /api/poles/memoire/flag``       — (dé)protège un fait (toggle ``important``).
- ``POST /api/poles/memoire/clean``      — exécute la liste **validée** (suppression
  gardée — un fait ``important`` est toujours refusé).
- ``GET/PUT /api/poles/memoire/policy``  — lit / met à jour l'activation par pôle.
- ``GET  /api/poles/memoire/wiring``     — audit du câblage ``reads_cross_pole``.
- ``GET  /api/poles/memoire/history``    — historique des passages du cleaner.

``POLES_DIR`` est un global de module → patchable en test.
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel

from argos_ops.poles.config import POLES_DIR, list_poles, load_all_poles
from argos_ops.poles.memoire import cleaner, history, wiring
from argos_ops.poles.memoire.cleaner import DeletionTarget
from argos_ops.poles.memoire.curation import CurationPlan, plan_curation
from argos_ops.poles.memoire.policy import MemoryPolicy, load_policy, set_pole_active
from argos_ops.poles.memory import (
    MemoryRecord,
    flag_important,
    read_pole_memory,
    read_record,
)

router = APIRouter(prefix="/api/poles/memoire", tags=["poles", "memoire"])


# =============================================================================
# Schemas — sortie
# =============================================================================
class MemoryFactOut(BaseModel):
    id: str
    pole: str
    script: str
    kind: str
    important: bool
    tags: list[str]
    body: str
    source: str | None
    created_at: datetime


class FactDetailOut(BaseModel):
    """Détail **complet** d'un fait précis (corps INTÉGRAL, jamais tronqué).

    Alimente la prévisualisation « contenu complet avant suppression » du
    cockpit Mémoire : le navigateur (``/browse``) et le plan (``/plan``)
    n'exposent qu'un ``body_preview`` ; cet endpoint relit le fait sur disque
    et renvoie le corps entier.
    """

    id: str
    pole: str
    script: str
    kind: str
    important: bool
    tags: list[str]
    body: str
    source: str | None
    created_at: datetime


class PoleMemoryStat(BaseModel):
    pole: str
    name: str
    active: bool
    n_facts: int
    n_important: int
    n_scripts: int
    scripts: list[str]
    last_activity: datetime | None
    n_candidates: int


class PolicyOut(BaseModel):
    protect_important: bool
    active_for: list[str]
    protected_kinds: list[str]
    protected_tags: list[str]
    protected_sources: list[str]
    default_ttl_days: int
    keep_recent_per_kind: int
    min_stale_days: int


class WiringEdgeOut(BaseModel):
    source: str
    target: str
    via_wildcard: bool
    target_facts: int


class WiringAnomalyOut(BaseModel):
    kind: str
    pole: str
    detail: str
    severity: str


class WiringOut(BaseModel):
    generated_at: datetime
    poles: list[str]
    edges: list[WiringEdgeOut]
    anomalies: list[WiringAnomalyOut]
    should_alert: bool
    summary: str
    n_edges: int
    n_warning: int


class HistoryItemOut(BaseModel):
    script: str
    record_id: str
    kind: str
    reason: str


class HistoryEntryOut(BaseModel):
    at: datetime
    pole: str
    actor: str
    deleted: list[HistoryItemOut]
    refused: list[HistoryItemOut]
    n_deleted: int
    n_refused: int


class MemoireCounts(BaseModel):
    poles_total: int
    poles_active: int
    facts_total: int
    important_total: int
    candidates_total: int
    wiring_warnings: int


class MemoireOverview(BaseModel):
    pole: str
    generated_at: datetime
    policy: PolicyOut
    poles: list[PoleMemoryStat]
    wiring: WiringOut
    history: list[HistoryEntryOut]
    counts: MemoireCounts


class BrowseOut(BaseModel):
    pole: str | None
    records: list[MemoryFactOut]
    poles: list[str]
    scripts: list[str]
    kinds: list[str]
    total: int
    important: int


class DeletionCandidateOut(BaseModel):
    pole: str
    script: str
    record_id: str
    kind: str
    created_at: datetime
    age_days: int
    reason: str
    detail: str
    body_preview: str


class ProtectedFactOut(BaseModel):
    pole: str
    script: str
    record_id: str
    kind: str
    created_at: datetime
    age_days: int
    reason: str
    would_delete: bool
    would_delete_reason: str | None
    detail: str
    body_preview: str


class PlanOut(BaseModel):
    pole: str
    active: bool
    generated_at: datetime
    scanned: int
    kept: int
    n_delete: int
    n_protected: int
    n_important: int
    n_saved_from_delete: int
    to_delete: list[DeletionCandidateOut]
    protected: list[ProtectedFactOut]


class CleanupResultOut(BaseModel):
    pole: str
    requested: int
    n_deleted: int
    n_refused: int
    skipped: int
    deleted: list[HistoryItemOut]
    refused: list[HistoryItemOut]


# =============================================================================
# Schemas — entrée
# =============================================================================
class FlagPayload(BaseModel):
    pole: str
    script: str
    record_id: str
    important: bool


class CleanTarget(BaseModel):
    script: str
    record_id: str


class CleanPayload(BaseModel):
    pole: str
    targets: list[CleanTarget]


class PolicyUpdatePayload(BaseModel):
    pole: str
    active: bool


# =============================================================================
# Helpers
# =============================================================================
def _fact_out(record: MemoryRecord) -> MemoryFactOut:
    return MemoryFactOut(
        id=record.id,
        pole=record.pole,
        script=record.script,
        kind=record.kind,
        important=record.important,
        tags=list(record.tags),
        body=record.body,
        source=record.source,
        created_at=record.created_at,
    )


def _fact_detail_out(record: MemoryRecord) -> FactDetailOut:
    return FactDetailOut(
        id=record.id,
        pole=record.pole,
        script=record.script,
        kind=record.kind,
        important=record.important,
        tags=list(record.tags),
        body=record.body,
        source=record.source,
        created_at=record.created_at,
    )


def _policy_out(policy: MemoryPolicy) -> PolicyOut:
    return PolicyOut(
        protect_important=policy.protect_important,
        active_for=list(policy.active_for),
        protected_kinds=list(policy.protected_kinds),
        protected_tags=list(policy.protected_tags),
        protected_sources=list(policy.protected_sources),
        default_ttl_days=policy.default_ttl_days,
        keep_recent_per_kind=policy.keep_recent_per_kind,
        min_stale_days=policy.min_stale_days,
    )


def _wiring_out(audit: wiring.WiringAudit) -> WiringOut:
    return WiringOut(
        generated_at=audit.generated_at,
        poles=list(audit.poles),
        edges=[
            WiringEdgeOut(
                source=e.source,
                target=e.target,
                via_wildcard=e.via_wildcard,
                target_facts=e.target_facts,
            )
            for e in audit.edges
        ],
        anomalies=[
            WiringAnomalyOut(kind=a.kind, pole=a.pole, detail=a.detail, severity=a.severity)
            for a in audit.anomalies
        ],
        should_alert=audit.should_alert,
        summary=audit.summary,
        n_edges=audit.n_edges,
        n_warning=audit.n_warning,
    )


def _history_out(entry: history.HistoryEntry) -> HistoryEntryOut:
    return HistoryEntryOut(
        at=entry.at,
        pole=entry.pole,
        actor=entry.actor,
        deleted=[
            HistoryItemOut(script=i.script, record_id=i.record_id, kind=i.kind, reason=i.reason)
            for i in entry.deleted
        ],
        refused=[
            HistoryItemOut(script=i.script, record_id=i.record_id, kind=i.kind, reason=i.reason)
            for i in entry.refused
        ],
        n_deleted=entry.n_deleted,
        n_refused=entry.n_refused,
    )


def _plan_out(plan: CurationPlan) -> PlanOut:
    return PlanOut(
        pole=plan.pole,
        active=plan.active,
        generated_at=plan.generated_at,
        scanned=plan.scanned,
        kept=plan.kept,
        n_delete=plan.n_delete,
        n_protected=plan.n_protected,
        n_important=plan.n_important,
        n_saved_from_delete=plan.n_saved_from_delete,
        to_delete=[
            DeletionCandidateOut(
                pole=c.pole,
                script=c.script,
                record_id=c.record_id,
                kind=c.kind,
                created_at=c.created_at,
                age_days=c.age_days,
                reason=c.reason,
                detail=c.detail,
                body_preview=c.body_preview,
            )
            for c in plan.to_delete
        ],
        protected=[
            ProtectedFactOut(
                pole=p.pole,
                script=p.script,
                record_id=p.record_id,
                kind=p.kind,
                created_at=p.created_at,
                age_days=p.age_days,
                reason=p.reason,
                would_delete=p.would_delete,
                would_delete_reason=p.would_delete_reason,
                detail=p.detail,
                body_preview=p.body_preview,
            )
            for p in plan.protected
        ],
    )


def _require_pole(pole: str) -> None:
    if pole not in list_poles(poles_root=POLES_DIR, include_internal=True):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Pôle inconnu : {pole}")


def _last_activity(records: list[MemoryRecord]) -> datetime | None:
    return max((r.created_at for r in records), default=None)


# =============================================================================
# Lecture
# =============================================================================
@router.get("/overview", response_model=MemoireOverview)
async def get_overview() -> MemoireOverview:
    """Tout ce dont l'onglet Mémoire a besoin en un seul fetch."""
    policy = load_policy(poles_root=POLES_DIR)
    configs = load_all_poles(poles_root=POLES_DIR)

    stats: list[PoleMemoryStat] = []
    facts_total = 0
    important_total = 0
    candidates_total = 0
    for cfg in configs:
        by_script = await read_pole_memory(cfg.id, poles_root=POLES_DIR)
        records = [r for recs in by_script.values() for r in recs]
        plan = plan_curation(by_script, policy, cfg.id)
        n_important = sum(1 for r in records if r.important)
        facts_total += len(records)
        important_total += n_important
        candidates_total += plan.n_delete
        stats.append(
            PoleMemoryStat(
                pole=cfg.id,
                name=cfg.name,
                active=policy.is_active(cfg.id),
                n_facts=len(records),
                n_important=n_important,
                n_scripts=len(by_script),
                scripts=sorted(by_script.keys()),
                last_activity=_last_activity(records),
                n_candidates=plan.n_delete,
            )
        )

    audit = await wiring.audit_wiring(poles_root=POLES_DIR)
    runs = history.load_runs(limit=20, poles_root=POLES_DIR)

    return MemoireOverview(
        pole="memoire",
        generated_at=datetime.now(UTC),
        policy=_policy_out(policy),
        poles=stats,
        wiring=_wiring_out(audit),
        history=[_history_out(e) for e in runs],
        counts=MemoireCounts(
            poles_total=len(configs),
            poles_active=sum(1 for s in stats if s.active),
            facts_total=facts_total,
            important_total=important_total,
            candidates_total=candidates_total,
            wiring_warnings=audit.n_warning,
        ),
    )


@router.get("/browse", response_model=BrowseOut)
async def browse(
    pole: str | None = Query(default=None),
    script: str | None = Query(default=None),
    q: str | None = Query(default=None),
    important: bool | None = Query(default=None),
) -> BrowseOut:
    """Navigateur mémoire : faits filtrés + facettes (pôles / scripts / kinds)."""
    target_poles = [pole] if pole else list_poles(poles_root=POLES_DIR, include_internal=True)
    if pole:
        _require_pole(pole)

    all_records: list[MemoryRecord] = []
    for p in target_poles:
        by_script = await read_pole_memory(p, poles_root=POLES_DIR)
        for recs in by_script.values():
            all_records.extend(recs)

    needle = (q or "").strip().lower()
    filtered = [
        r
        for r in all_records
        if (script is None or r.script == script)
        and (important is None or r.important == important)
        and (not needle or needle in r.body.lower() or needle in r.kind.lower())
    ]
    filtered.sort(key=lambda r: r.created_at, reverse=True)

    return BrowseOut(
        pole=pole,
        records=[_fact_out(r) for r in filtered],
        poles=sorted({r.pole for r in all_records}),
        scripts=sorted({r.script for r in all_records}),
        kinds=sorted({r.kind for r in all_records}),
        total=len(filtered),
        important=sum(1 for r in filtered if r.important),
    )


@router.get("/fact", response_model=FactDetailOut)
async def get_fact(
    pole: str = Query(...),
    script: str = Query(...),
    record_id: str = Query(...),
) -> FactDetailOut:
    """Détail complet d'un fait (corps INTÉGRAL) — preview avant suppression.

    Relit le fait sur disque par ``(pole, script, record_id)`` et renvoie le
    corps entier (le navigateur/plan ne montrent qu'un aperçu tronqué). 404 si
    le pôle est inconnu ou le fait introuvable / illisible.
    """
    _require_pole(pole)
    record = await read_record(pole, script, record_id, poles_root=POLES_DIR)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Fait introuvable : {pole}/{script}/{record_id}",
        )
    return _fact_detail_out(record)


@router.get("/plan", response_model=PlanOut)
async def get_plan(pole: str = Query(...)) -> PlanOut:
    """Plan de curation d'un pôle (PREVIEW avant validation humaine)."""
    _require_pole(pole)
    by_script = await read_pole_memory(pole, poles_root=POLES_DIR)
    policy = load_policy(poles_root=POLES_DIR)
    plan = plan_curation(by_script, policy, pole)
    return _plan_out(plan)


@router.get("/wiring", response_model=WiringOut)
async def get_wiring() -> WiringOut:
    """Audit complet du câblage ``reads_cross_pole`` de la flotte."""
    return _wiring_out(await wiring.audit_wiring(poles_root=POLES_DIR))


@router.get("/policy", response_model=PolicyOut)
async def get_policy() -> PolicyOut:
    """Policy de curation courante."""
    return _policy_out(load_policy(poles_root=POLES_DIR))


@router.get("/history", response_model=list[HistoryEntryOut])
async def get_history(limit: int = Query(default=50, ge=1, le=500)) -> list[HistoryEntryOut]:
    """Historique des passages du cleaner (du plus récent au plus ancien)."""
    return [_history_out(e) for e in history.load_runs(limit=limit, poles_root=POLES_DIR)]


# =============================================================================
# Mutations
# =============================================================================
@router.post("/flag", response_model=MemoryFactOut)
async def set_flag(payload: FlagPayload) -> MemoryFactOut:
    """(Dé)protège un fait : toggle ``important``. 404 si le fait est introuvable."""
    _require_pole(payload.pole)
    record = await flag_important(
        payload.pole,
        payload.script,
        payload.record_id,
        important=payload.important,
        poles_root=POLES_DIR,
    )
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Fait introuvable : {payload.pole}/{payload.script}/{payload.record_id}",
        )
    return _fact_out(record)


@router.post("/clean", response_model=CleanupResultOut)
async def clean(payload: CleanPayload) -> CleanupResultOut:
    """Exécute la liste **validée** (suppression gardée).

    Double garde-fou « Python tranche » : un fait ``important`` ou pattern-protégé
    est **toujours refusé** (jamais supprimé), même s'il figure dans la requête ;
    et une cible non éligible (ni périmée ni stale) est refusée. Idempotent.
    """
    _require_pole(payload.pole)
    targets = [DeletionTarget(t.script, t.record_id) for t in payload.targets]
    result = await cleaner.execute_cleanup(
        payload.pole, targets, actor="cockpit", poles_root=POLES_DIR
    )
    return CleanupResultOut(
        pole=result.pole,
        requested=result.requested,
        n_deleted=result.n_deleted,
        n_refused=result.n_refused,
        skipped=result.skipped,
        deleted=[
            HistoryItemOut(script=i.script, record_id=i.record_id, kind=i.kind, reason=i.reason)
            for i in result.deleted
        ],
        refused=[
            HistoryItemOut(script=i.script, record_id=i.record_id, kind=i.kind, reason=i.reason)
            for i in result.refused
        ],
    )


@router.put("/policy", response_model=PolicyOut)
async def update_policy(payload: PolicyUpdatePayload) -> PolicyOut:
    """(Dé)active la curation d'un pôle. 404 si le pôle est inconnu."""
    _require_pole(payload.pole)
    updated = set_pole_active(payload.pole, payload.active, poles_root=POLES_DIR)
    return _policy_out(updated)


__all__ = ["router"]
