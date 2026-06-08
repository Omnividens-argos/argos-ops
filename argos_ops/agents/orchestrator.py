"""OrchestratorBot — chef de fleet Argos Ops (P22.B Meta-Ops core).

Version minimale Sprint 1 — décide quels agents doivent tourner
maintenant à partir de :

- la cadence cron attendue (déclarée dans :data:`AGENT_FLEET`)
- la dernière exécution en DB (``agent_runs.started_at`` via
  :func:`get_last_run_per_agent`)
- la config runtime (``enabled``, ``paused_until``, ``daily_limit``,
  ``intensity_level``) lue via :func:`get_agent_config`
- l'état des breakers (:func:`is_breaker_tripped`)
- le nombre de runs déjà comptabilisés aujourd'hui
  (:func:`count_runs_today`)

Modes :
- ``dry-run`` (défaut) — logue le plan et la raison de chaque décision,
  ne lance rien. Utilisable depuis le slash command ``/orchestrate``
  pour debug.
- ``live`` — déclenche via :func:`argos_ops.agents.base.run_agent`
  (qui ré-applique le runtime guard P15/P16.B). Garde-fou parallélisme
  via ``max_concurrent`` (default 2) pour ne pas saturer le quota
  Claude Pro Max.

Préparation P20/P21 — deux hooks ``_consume_memory()`` et
``_consume_capabilities()`` retournent ``{}`` pour l'instant. Ils
seront branchés respectivement sur Argos Memory (mémoire vivante
partagée) et le Capabilities registry (routage pull-based) quand
ces partis seront livrés.

Cf. plan ``docs/ARGOS_OPS_PLAN.md`` Annexe D § 12 Meta-Ops, Sprint 1.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from argos_ops.agents.base import BaseAgent, IOItem, RunResult, run_agent
from argos_ops.agents.bot_health import BotHealthBot
from argos_ops.agents.digest_builder import DigestBuilder
from argos_ops.agents.email_bot import EmailBot
from argos_ops.agents.finance_bot import FinanceBot
from argos_ops.crm.db import session_scope
from argos_ops.crm.repository import (
    count_runs_today,
    get_agent_config,
    get_last_run_per_agent,
    is_breaker_tripped,
)

DecisionVerdict = Literal[
    "launch",
    "skipped_disabled",
    "skipped_paused",
    "skipped_daily_limit",
    "skipped_breaker",
    "skipped_not_due",
    "skipped_intensity_zero",
]


@dataclass(frozen=True)
class FleetEntry:
    """Déclaration d'un agent orchestrable.

    ``interval_hours`` = cadence cron canonique attendue. Si le dernier
    run remonte à plus que cette valeur, l'agent est marqué « due ».
    Pour les agents très fréquents (EmailBot toutes les 15 min ≈ 0.25 h)
    cette logique reste robuste : on relance si en retard, on skip
    sinon.

    ``factory`` = callable sans argument qui retourne une instance fraîche
    de l'agent. On évite de stocker l'instance directement pour ne pas
    partager d'état entre runs.
    """

    name: str
    interval_hours: float
    factory: Callable[[], BaseAgent]
    breaker_name: str | None = None


@dataclass(frozen=True)
class AgentDecision:
    """Verdict orchestrateur pour un agent à un instant t."""

    agent_name: str
    verdict: DecisionVerdict
    reason: str
    last_run_at: datetime | None
    age_hours: float | None
    interval_hours: float
    enabled: bool
    intensity_level: int
    runs_today: int
    daily_limit: int | None


@dataclass
class OrchestrationPlan:
    """Résultat de :func:`plan_execution`."""

    decisions: list[AgentDecision]
    max_concurrent: int
    dry_run: bool
    generated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def to_launch(self) -> list[AgentDecision]:
        return [d for d in self.decisions if d.verdict == "launch"]

    @property
    def skipped(self) -> list[AgentDecision]:
        return [d for d in self.decisions if d.verdict != "launch"]

    def summary(self) -> str:
        return (
            f"{len(self.to_launch)} to launch · {len(self.skipped)} skipped"
            f" (max_concurrent={self.max_concurrent}, dry_run={self.dry_run})"
        )


@dataclass(frozen=True)
class ExecutionOutcome:
    """Résultat d'une exécution live d'un agent (live mode)."""

    agent_name: str
    status: str  # success / failed / killed_by_breaker / skipped_*
    output_summary: str | None
    error: str | None


# =============================================================================
# Catalogue Python de la flotte orchestrable
# =============================================================================
# Sprint 1 : 4 bots actifs avec cadence cron canonique.
# - DigestBuilder : 24 h (cron 0 8 * * *)
# - EmailBot      : 0.25 h (cron */15 8-22 * * *)
# - FinanceBot    : 24 h (cron 0 6 * * *)
# - BotHealthBot  : 2 h (cron Task Scheduler P22.B)
#
# SupportBot est interactif (slash) — pas de cadence donc absent.
# Quand un nouveau bot planifié rejoint la flotte, l'ajouter ici.
AGENT_FLEET: tuple[FleetEntry, ...] = (
    FleetEntry(
        name="DigestBuilder",
        interval_hours=24.0,
        factory=DigestBuilder,
        breaker_name="DigestBuilder",
    ),
    FleetEntry(
        name="EmailBot",
        interval_hours=0.25,
        factory=EmailBot,
        breaker_name="email_smtp_failures_burst",
    ),
    FleetEntry(
        name="FinanceBot",
        interval_hours=24.0,
        factory=FinanceBot,
        breaker_name="stripe_api_error_burst",
    ),
    FleetEntry(
        name="BotHealthBot",
        interval_hours=2.0,
        factory=BotHealthBot,
        breaker_name=None,
    ),
)

DEFAULT_MAX_CONCURRENT = 2


# =============================================================================
# Hooks d'extension P20 / P21 (placeholders Sprint 1)
# =============================================================================
async def _consume_memory(agent_name: str) -> dict[str, Any]:
    """Hook P20 — Argos Memory (mémoire vivante partagée).

    Retourne ``{}`` tant que P20.A n'est pas livré. Sera branché sur
    le module ``argos_ops.memory`` pour fournir à chaque agent un
    contexte mémoire (décisions passées, leads connus, conventions).
    """
    return {}


async def _consume_capabilities(agent_name: str) -> dict[str, Any]:
    """Hook P21 — Capabilities (routage pull-based).

    Retourne ``{}`` tant que P21 n'est pas livré. Sera branché sur
    le registre de capabilities pour permettre à l'orchestrateur de
    router une demande vers le bot le plus qualifié plutôt que de
    suivre un planning statique.
    """
    return {}


# =============================================================================
# Planification
# =============================================================================
def _compute_age_hours(last_run_at: datetime | None, *, now: datetime) -> float | None:
    if last_run_at is None:
        return None
    started = last_run_at
    if started.tzinfo is None:
        started = started.replace(tzinfo=UTC)
    return (now - started).total_seconds() / 3600.0


async def _decide_one(
    session: AsyncSession,
    entry: FleetEntry,
    *,
    last_run_at: datetime | None,
    now: datetime,
) -> AgentDecision:
    """Construit l'AgentDecision pour un agent — pure-ish (DB-bound)."""
    # Hooks P20/P21 — placeholders, on les appelle pour éviter de les
    # oublier au moment du câblage et pour que les tests vérifient
    # qu'ils sont invoqués.
    await _consume_memory(entry.name)
    await _consume_capabilities(entry.name)

    config = await get_agent_config(session, entry.name)
    runs_today = await count_runs_today(session, entry.name)
    age_hours = _compute_age_hours(last_run_at, now=now)

    base_args: dict[str, Any] = {
        "agent_name": entry.name,
        "last_run_at": last_run_at,
        "age_hours": round(age_hours, 2) if age_hours is not None else None,
        "interval_hours": entry.interval_hours,
        "enabled": config.enabled,
        "intensity_level": config.intensity_level,
        "runs_today": runs_today,
        "daily_limit": config.daily_limit,
    }

    # 1. Breaker tripped — priorité absolue (cohérent avec runtime guard)
    if entry.breaker_name is not None and await is_breaker_tripped(session, entry.breaker_name):
        return AgentDecision(
            verdict="skipped_breaker",
            reason=f"breaker '{entry.breaker_name}' tripped",
            **base_args,
        )

    # 2. Disabled via Admin Panel
    if not config.enabled:
        return AgentDecision(
            verdict="skipped_disabled",
            reason="agent disabled via Admin Panel",
            **base_args,
        )

    # 3. Paused temporairement
    if config.paused_until is not None:
        paused_until = config.paused_until
        if paused_until.tzinfo is None:
            paused_until = paused_until.replace(tzinfo=UTC)
        if paused_until > now:
            return AgentDecision(
                verdict="skipped_paused",
                reason=f"paused until {paused_until.isoformat()}",
                **base_args,
            )

    # 4. Daily limit atteint
    if (
        config.daily_limit is not None
        and config.daily_limit > 0
        and runs_today >= config.daily_limit
    ):
        return AgentDecision(
            verdict="skipped_daily_limit",
            reason=f"daily_limit reached ({runs_today}/{config.daily_limit})",
            **base_args,
        )

    # 5. Intensity = 0 → équivaut à pause silencieuse
    if config.intensity_level <= 0:
        return AgentDecision(
            verdict="skipped_intensity_zero",
            reason="intensity_level=0 (silent pause)",
            **base_args,
        )

    # 6. Pas encore due selon la cadence
    if age_hours is not None and age_hours < entry.interval_hours:
        return AgentDecision(
            verdict="skipped_not_due",
            reason=(f"last run {age_hours:.2f}h ago < interval {entry.interval_hours}h"),
            **base_args,
        )

    # 7. Tout passe → launch
    reason = (
        "never run, due"
        if age_hours is None
        else f"due since {age_hours - entry.interval_hours:.2f}h"
    )
    return AgentDecision(verdict="launch", reason=reason, **base_args)


async def plan_execution(
    *,
    fleet: tuple[FleetEntry, ...] = AGENT_FLEET,
    max_concurrent: int = DEFAULT_MAX_CONCURRENT,
    dry_run: bool = True,
    now: datetime | None = None,
) -> OrchestrationPlan:
    """Construit l'OrchestrationPlan en lisant toute la fleet d'un coup.

    Ne déclenche aucun agent — la décision d'exécuter est laissée à
    :func:`execute_plan`. Permet d'inspecter le plan dans le slash
    command ``/orchestrate`` (mode dry-run) avant de switcher en live.
    """
    now = now or datetime.now(UTC)
    async with session_scope() as session:
        last_runs = await get_last_run_per_agent(session)
        decisions: list[AgentDecision] = []
        for entry in fleet:
            last_run = last_runs.get(entry.name)
            decisions.append(
                await _decide_one(
                    session,
                    entry,
                    last_run_at=last_run.started_at if last_run else None,
                    now=now,
                )
            )

    # Priorité d'exécution : agents les plus en retard d'abord (oldest
    # due first). Les agents jamais run passent en tête (age=None traité
    # comme +infini). Limite l'effet « EmailBot toutes les 15 min monopolise
    # le throughput » : il reste prioritaire seulement si tout le monde
    # tourne dans les clous.
    def _retard(d: AgentDecision) -> float:
        if d.verdict != "launch":
            return -1.0
        if d.age_hours is None:
            return float("inf")
        return d.age_hours - d.interval_hours

    decisions.sort(key=lambda d: (-_retard(d), d.agent_name))
    return OrchestrationPlan(
        decisions=decisions,
        max_concurrent=max_concurrent,
        dry_run=dry_run,
        generated_at=now,
    )


# =============================================================================
# Exécution live — parallélisme capé via semaphore
# =============================================================================
async def execute_plan(
    plan: OrchestrationPlan,
    *,
    fleet: tuple[FleetEntry, ...] = AGENT_FLEET,
    runner: Callable[[BaseAgent], Awaitable[RunResult]] = run_agent,
) -> list[ExecutionOutcome]:
    """Lance les agents marqués ``launch`` avec un sémaphore de
    parallélisme.

    Le ``runner`` est injectable pour faciliter les tests unitaires (on
    passe un fake qui ne fait pas d'I/O). Production utilise
    :func:`argos_ops.agents.base.run_agent` qui ré-applique le runtime
    guard côté DB — donc même en live, si le breaker trippe entre la
    planification et l'exécution, l'agent est court-circuité proprement.
    """
    if plan.dry_run:
        return []

    by_name: dict[str, FleetEntry] = {e.name: e for e in fleet}
    to_run = plan.to_launch
    if not to_run:
        return []

    sem = asyncio.Semaphore(max(1, plan.max_concurrent))

    async def _run_one(decision: AgentDecision) -> ExecutionOutcome:
        entry = by_name.get(decision.agent_name)
        if entry is None:
            return ExecutionOutcome(
                agent_name=decision.agent_name,
                status="failed",
                output_summary=None,
                error=f"agent '{decision.agent_name}' absent de la fleet — incohérence plan/exec",
            )
        async with sem:
            logger.info(f"Orchestrator → launch {decision.agent_name}")
            agent = entry.factory()
            result = await runner(agent)
            return ExecutionOutcome(
                agent_name=decision.agent_name,
                status=result.status,
                output_summary=result.output_summary,
                error=result.error,
            )

    return await asyncio.gather(*(_run_one(d) for d in to_run))


# =============================================================================
# Agent
# =============================================================================
class OrchestratorBot(BaseAgent):
    """Chef de fleet — décide quels bots doivent tourner maintenant."""

    name = "OrchestratorBot"
    command = "/orchestrate"
    breaker_name = None  # pas de breaker dédié : il les observe
    ai_act_risk_class = "minimal"

    def __init__(
        self,
        *,
        fleet: tuple[FleetEntry, ...] = AGENT_FLEET,
        max_concurrent: int = DEFAULT_MAX_CONCURRENT,
        live: bool = False,
    ) -> None:
        self._fleet = fleet
        self._max_concurrent = max_concurrent
        self._live = live

    async def run(self) -> RunResult:
        plan = await plan_execution(
            fleet=self._fleet,
            max_concurrent=self._max_concurrent,
            dry_run=not self._live,
        )
        for decision in plan.decisions:
            line = (
                f"[{decision.verdict}] {decision.agent_name} — "
                f"age={decision.age_hours}h interval={decision.interval_hours}h "
                f"runs_today={decision.runs_today} reason={decision.reason}"
            )
            if decision.verdict == "launch":
                logger.info(line)
            else:
                logger.debug(line)

        orchestration_inputs = [
            IOItem(
                label="Cadence cron de la flotte",
                kind="other",
                detail="intervalle canonique par bot (AGENT_FLEET)",
                count=len(self._fleet),
            ),
            IOItem(
                label="Dernier run par agent",
                kind="db",
                detail="agent_runs.started_at · âge vs cadence",
            ),
            IOItem(
                label="Config runtime + breakers",
                kind="db",
                detail="agent_config (enabled/paused/daily_limit/intensity) + breakers tripped",
            ),
        ]

        if not self._live:
            logger.info(f"OrchestratorBot dry-run — {plan.summary()}")
            return RunResult(
                status="success",
                output_summary=f"dry-run · {plan.summary()}",
                inputs=orchestration_inputs,
                outputs=[
                    IOItem(
                        label="Plan d'exécution (dry-run)",
                        kind="other",
                        detail=(
                            f"{len(plan.to_launch)} à lancer · {len(plan.skipped)} skippés "
                            "(aucun lancement)"
                        ),
                        count=len(plan.to_launch),
                    )
                ],
                extras={
                    "dry_run": True,
                    "to_launch": [d.agent_name for d in plan.to_launch],
                    "skipped": [
                        {"agent": d.agent_name, "verdict": d.verdict} for d in plan.skipped
                    ],
                },
            )

        outcomes = await execute_plan(plan, fleet=self._fleet)
        ok = sum(1 for o in outcomes if o.status == "success")
        failed = sum(1 for o in outcomes if o.status != "success")
        logger.info(f"OrchestratorBot live — launched {len(outcomes)} ({ok} ok, {failed} failed)")
        return RunResult(
            status="success",
            output_summary=(f"live · launched={len(outcomes)} ok={ok} failed={failed}"),
            inputs=orchestration_inputs,
            outputs=[
                IOItem(
                    label="Bots lancés (live)",
                    kind="other",
                    detail=f"{ok} ok · {failed} en échec",
                    count=len(outcomes),
                )
            ],
            extras={
                "dry_run": False,
                "outcomes": [
                    {"agent": o.agent_name, "status": o.status, "error": o.error} for o in outcomes
                ],
            },
        )


__all__ = [
    "AGENT_FLEET",
    "DEFAULT_MAX_CONCURRENT",
    "AgentDecision",
    "DecisionVerdict",
    "ExecutionOutcome",
    "FleetEntry",
    "OrchestrationPlan",
    "OrchestratorBot",
    "execute_plan",
    "plan_execution",
]
