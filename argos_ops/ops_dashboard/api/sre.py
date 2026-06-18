"""Endpoints cockpit du pôle **SRE / Meta-Ops** (archi v2, S8).

Sert au shell ``poles.html`` tout l'onglet SRE, 100 % fichiers / local-first
(D-017) — tout est recalculé à chaud depuis le runlog + les fichiers d'état du
pôle (``breakers.yaml`` / ``killswitch.yaml`` / ``orchestrator.yaml``) et les
``pole.yaml`` de la flotte :

- ``GET  /api/poles/sre/overview``          — statut temps réel + breakers + kill-switch
  + planning cron + plan orchestrateur + runs récents + compteurs.
- ``GET  /api/poles/sre/runs``              — historique des runs (filtre script).
- ``GET  /api/poles/sre/plan``              — plan orchestrateur (dry-run).
- ``POST /api/poles/sre/run/{script}``      — lance un script maintenant.
- ``POST /api/poles/sre/breakers/{name}/reset`` / ``/trip`` — gère un breaker.
- ``POST /api/poles/sre/killswitch``        — gèle/dégèle la flotte (global).
- ``POST /api/poles/sre/killswitch/script`` — gèle/dégèle un script ciblé.

``POLES_DIR`` est un global de module → patchable en test.
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel

from argos_ops.poles.base import run_script
from argos_ops.poles.config import POLES_DIR
from argos_ops.poles.sre import breakers, orchestrator, runlog, schedule
from argos_ops.poles.sre import killswitch as ks_mod
from argos_ops.poles.sre import status as status_mod
from argos_ops.poles.sre.report import Severity
from argos_ops.poles.sre.scripts import RUNNABLE

router = APIRouter(prefix="/api/poles/sre", tags=["poles", "sre"])

SRE_POLE = "sre"


# =============================================================================
# Schemas — sortie
# =============================================================================
class ScriptStatusOut(BaseModel):
    script: str
    description: str
    schedule: str | None
    health: Severity
    last_status: str | None
    last_severity: Severity | None
    last_summary: str | None
    last_run_at: datetime | None
    age_hours: float | None
    next_run_at: datetime | None
    due: bool
    stale: bool
    frozen: bool
    breaker_tripped: bool
    p50_ms: float | None
    p95_ms: float | None
    n_runs: int
    runnable: bool


class RunOut(BaseModel):
    at: datetime
    script: str
    status: str
    severity: Severity
    duration_ms: float
    summary: str
    error: str | None


class BreakerOut(BaseModel):
    name: str
    tripped: bool
    reason: str | None
    tripped_at: datetime | None
    age_hours: float | None


class KillSwitchOut(BaseModel):
    frozen: bool
    reason: str | None
    frozen_scripts: list[str]
    updated_at: datetime | None


class ScheduleEntryOut(BaseModel):
    pole: str
    script: str
    schedule: str | None
    last_run_at: datetime | None
    next_run_at: datetime | None
    due: bool
    missed: int


class DecisionOut(BaseModel):
    script: str
    verdict: str
    reason: str
    schedule: str | None
    last_run_at: datetime | None
    next_run_at: datetime | None
    runs_today: int
    daily_limit: int | None
    runnable: bool


class PlanOut(BaseModel):
    generated_at: datetime
    dry_run: bool
    max_concurrent: int
    summary: str
    to_launch: int
    decisions: list[DecisionOut]


class SreCounts(BaseModel):
    scripts_total: int
    green: int
    yellow: int
    red: int
    frozen: int
    breakers_tripped: int
    due_now: int
    runs_24h: int


class SreOverview(BaseModel):
    pole: str
    generated_at: datetime
    health: Severity
    counts: SreCounts
    scripts: list[ScriptStatusOut]
    breakers: list[BreakerOut]
    killswitch: KillSwitchOut
    schedule: list[ScheduleEntryOut]
    plan: PlanOut
    recent_runs: list[RunOut]


class RunResultOut(BaseModel):
    script: str
    status: str
    summary: str | None
    error: str | None


# =============================================================================
# Schemas — entrée
# =============================================================================
class TripPayload(BaseModel):
    reason: str = "déclenché manuellement (cockpit)"


class KillSwitchPayload(BaseModel):
    frozen: bool
    reason: str | None = None


class KillSwitchScriptPayload(BaseModel):
    script: str
    frozen: bool


# =============================================================================
# Helpers
# =============================================================================
def _runnable_ids() -> set[str]:
    return set(RUNNABLE)


def _status_out(row: status_mod.ScriptStatus, runnable: set[str]) -> ScriptStatusOut:
    return ScriptStatusOut(
        script=row.script,
        description=row.description,
        schedule=row.schedule,
        health=row.health,
        last_status=row.last_status,
        last_severity=row.last_severity,
        last_summary=row.last_summary,
        last_run_at=row.last_run_at,
        age_hours=row.age_hours,
        next_run_at=row.next_run_at,
        due=row.due,
        stale=row.stale,
        frozen=row.frozen,
        breaker_tripped=row.breaker_tripped,
        p50_ms=row.p50_ms,
        p95_ms=row.p95_ms,
        n_runs=row.n_runs,
        runnable=row.script in runnable,
    )


def _run_out(entry: runlog.RunLogEntry) -> RunOut:
    return RunOut(
        at=entry.at,
        script=entry.script,
        status=entry.status,
        severity=entry.severity,
        duration_ms=entry.duration_ms,
        summary=entry.summary,
        error=entry.error,
    )


def _breaker_out(b: breakers.Breaker) -> BreakerOut:
    return BreakerOut(
        name=b.name,
        tripped=b.tripped,
        reason=b.reason,
        tripped_at=b.tripped_at,
        age_hours=b.age_hours,
    )


def _ks_out(ks: ks_mod.KillSwitch) -> KillSwitchOut:
    return KillSwitchOut(
        frozen=ks.frozen,
        reason=ks.reason,
        frozen_scripts=list(ks.frozen_scripts),
        updated_at=ks.updated_at,
    )


def _decision_out(d: orchestrator.ScriptDecision) -> DecisionOut:
    return DecisionOut(
        script=d.script,
        verdict=d.verdict,
        reason=d.reason,
        schedule=d.schedule,
        last_run_at=d.last_run_at,
        next_run_at=d.next_run_at,
        runs_today=d.runs_today,
        daily_limit=d.daily_limit,
        runnable=d.runnable,
    )


def _plan_out(plan: orchestrator.OrchestrationPlan) -> PlanOut:
    return PlanOut(
        generated_at=plan.generated_at,
        dry_run=plan.dry_run,
        max_concurrent=plan.max_concurrent,
        summary=plan.summary(),
        to_launch=len(plan.to_launch),
        decisions=[_decision_out(d) for d in plan.decisions],
    )


# =============================================================================
# Lecture
# =============================================================================
@router.get("/overview", response_model=SreOverview)
async def get_overview() -> SreOverview:
    """Tout ce dont l'onglet SRE a besoin en un seul fetch."""
    now = datetime.now(UTC)
    rows = status_mod.compute_status(now=now, poles_root=POLES_DIR)
    runnable = _runnable_ids()
    tripped = breakers.load_breakers(poles_root=POLES_DIR)
    ks = ks_mod.load_killswitch(poles_root=POLES_DIR)

    last_runs = {
        f"{SRE_POLE}/{s}": e.at for s, e in runlog.latest_per_script(poles_root=POLES_DIR).items()
    }
    sched = schedule.fleet_schedule(last_runs=last_runs, now=now, poles_root=POLES_DIR)
    plan = await orchestrator.plan_execution(poles_root=POLES_DIR, now=now, dry_run=True)
    recent = runlog.load_runs(limit=40, poles_root=POLES_DIR)

    cutoff = now.timestamp() - 24 * 3600
    runs_24h = sum(1 for r in runlog.load_runs(poles_root=POLES_DIR) if r.at.timestamp() >= cutoff)

    return SreOverview(
        pole=SRE_POLE,
        generated_at=now,
        health=status_mod.fleet_health(rows),
        counts=SreCounts(
            scripts_total=len(rows),
            green=sum(1 for r in rows if r.health == "green"),
            yellow=sum(1 for r in rows if r.health == "yellow"),
            red=sum(1 for r in rows if r.health == "red"),
            frozen=sum(1 for r in rows if r.frozen),
            breakers_tripped=sum(1 for b in tripped.values() if b.tripped),
            due_now=sum(1 for r in rows if r.due),
            runs_24h=runs_24h,
        ),
        scripts=[_status_out(r, runnable) for r in rows],
        breakers=[_breaker_out(b) for b in sorted(tripped.values(), key=lambda x: x.name)],
        killswitch=_ks_out(ks),
        schedule=[
            ScheduleEntryOut(
                pole=e.pole,
                script=e.script,
                schedule=e.schedule,
                last_run_at=e.last_run_at,
                next_run_at=e.next_run_at,
                due=e.due,
                missed=e.missed,
            )
            for e in sched
        ],
        plan=_plan_out(plan),
        recent_runs=[_run_out(r) for r in recent],
    )


@router.get("/runs", response_model=list[RunOut])
async def get_runs(
    script: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
) -> list[RunOut]:
    """Historique des runs (du plus récent au plus ancien)."""
    return [_run_out(r) for r in runlog.load_runs(script=script, limit=limit, poles_root=POLES_DIR)]


@router.get("/plan", response_model=PlanOut)
async def get_plan() -> PlanOut:
    """Plan orchestrateur (dry-run) : qui tournerait maintenant et pourquoi."""
    plan = await orchestrator.plan_execution(poles_root=POLES_DIR, dry_run=True)
    return _plan_out(plan)


# =============================================================================
# Mutations
# =============================================================================
@router.post("/run/{script}", response_model=RunResultOut)
async def run_now(script: str) -> RunResultOut:
    """Lance un script SRE immédiatement. 404 si le script est inconnu."""
    cls = RUNNABLE.get(script)
    if cls is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Script SRE inconnu : {script}"
        )
    result = await run_script(cls(poles_root=POLES_DIR))
    return RunResultOut(
        script=script, status=result.status, summary=result.summary, error=result.error
    )


@router.post("/breakers/{name}/reset", response_model=BreakerOut)
async def reset_breaker(name: str) -> BreakerOut:
    """Désarme un breaker (reset humain)."""
    return _breaker_out(breakers.reset(name, poles_root=POLES_DIR))


@router.post("/breakers/{name}/trip", response_model=BreakerOut)
async def trip_breaker(name: str, payload: TripPayload) -> BreakerOut:
    """Arme manuellement un breaker (latch)."""
    return _breaker_out(breakers.trip(name, payload.reason, poles_root=POLES_DIR))


@router.post("/killswitch", response_model=KillSwitchOut)
async def set_killswitch(payload: KillSwitchPayload) -> KillSwitchOut:
    """Gèle / dégèle toute la flotte (kill-switch global)."""
    return _ks_out(ks_mod.set_global(payload.frozen, reason=payload.reason, poles_root=POLES_DIR))


@router.post("/killswitch/script", response_model=KillSwitchOut)
async def set_killswitch_script(payload: KillSwitchScriptPayload) -> KillSwitchOut:
    """Gèle / dégèle un script ciblé."""
    if payload.script not in RUNNABLE:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Script SRE inconnu : {payload.script}"
        )
    return _ks_out(ks_mod.set_script(payload.script, payload.frozen, poles_root=POLES_DIR))


__all__ = ["router"]
