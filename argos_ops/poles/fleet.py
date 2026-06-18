"""Orchestrateur de **flotte** — chef des 8 pôles (archi v2, S9).

Généralise l'orchestrateur SRE (:mod:`argos_ops.poles.sre.orchestrator`, qui ne
planifie que le pôle SRE) à **toute la flotte** : il décide quels scripts —
*tous pôles confondus* — doivent tourner maintenant, les lance (mode live), puis
**réveille l'agent** de chaque pôle dont des scripts ont rafraîchi la mémoire.
C'est le cycle complet **script → mémoire → agent → action**.

Sources de décision (toutes 100 % fichiers / local-first, D-017) :

- la **cadence cron** déclarée dans chaque ``pole.yaml`` (:mod:`argos_ops.poles.sre.schedule`) ;
- le **kill-switch** global / par script (:mod:`argos_ops.poles.sre.killswitch`) ;
- les **breakers** latch (:mod:`argos_ops.poles.sre.breakers`) ;
- une **limite quotidienne** par couple ``pole/script`` (``data/poles/fleet.yaml``),
  comptée sur le runlog partagé de la flotte.

Le câblage (qui sont les scripts / agents de chaque pôle) vit dans
:mod:`argos_ops.poles.registry`. Mode **dry-run** par défaut : on logue le plan,
on ne lance rien.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

import yaml
from loguru import logger

from argos_ops.poles.agent import AgentResult, BaseAgent
from argos_ops.poles.base import BaseScript, ScriptResult, run_script
from argos_ops.poles.config import POLES_DIR, load_all_poles
from argos_ops.poles.fleet_runlog import (
    FleetRun,
    append_fleet_run,
    latest_per_pole_script,
    load_fleet_runs,
    runs_today_for,
)
from argos_ops.poles.registry import POLE_ORDER, agent_class, script_registry
from argos_ops.poles.sre import breakers, schedule
from argos_ops.poles.sre.killswitch import load_killswitch

FLEET_CONFIG_FILE = "fleet.yaml"
DEFAULT_MAX_CONCURRENT = 2

DecisionVerdict = Literal[
    "launch",
    "skipped_frozen",
    "skipped_breaker",
    "skipped_not_due",
    "skipped_daily_limit",
    "skipped_no_schedule",
    "skipped_not_runnable",
]


# =============================================================================
# Configuration runtime
# =============================================================================
def fleet_config_path(*, poles_root: Path = POLES_DIR) -> Path:
    return poles_root / FLEET_CONFIG_FILE


@dataclass(frozen=True)
class FleetConfig:
    """Réglages runtime de l'orchestrateur de flotte.

    ``daily_limits`` est indexé par clé ``"pole/script"`` (ex.
    ``"vente/email_bot": 96``).
    """

    max_concurrent: int = DEFAULT_MAX_CONCURRENT
    daily_limits: dict[str, int] = field(default_factory=dict)

    def daily_limit(self, pole: str, script: str) -> int | None:
        return self.daily_limits.get(f"{pole}/{script}")


def load_fleet_config(*, poles_root: Path = POLES_DIR) -> FleetConfig:
    path = fleet_config_path(poles_root=poles_root)
    if not path.exists():
        return FleetConfig()
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        logger.warning(f"fleet — config invalide, défauts : {exc}")
        return FleetConfig()
    if not isinstance(raw, dict):
        return FleetConfig()
    limits: dict[str, int] = {}
    limits_raw = raw.get("daily_limits")
    if isinstance(limits_raw, dict):
        for k, v in limits_raw.items():
            try:
                limits[str(k)] = int(v)
            except (ValueError, TypeError):
                continue
    raw_mc = raw.get("max_concurrent")
    try:
        max_concurrent = DEFAULT_MAX_CONCURRENT if raw_mc is None else int(raw_mc)
    except (ValueError, TypeError):
        max_concurrent = DEFAULT_MAX_CONCURRENT
    return FleetConfig(max_concurrent=max(1, max_concurrent), daily_limits=limits)


# =============================================================================
# Décisions + plan
# =============================================================================
@dataclass(frozen=True)
class FleetDecision:
    """Verdict de l'orchestrateur pour un script d'un pôle."""

    pole: str
    script: str
    verdict: DecisionVerdict
    reason: str
    schedule: str | None
    last_run_at: datetime | None
    next_run_at: datetime | None
    runs_today: int
    daily_limit: int | None
    runnable: bool


@dataclass
class FleetPlan:
    """Plan complet de la flotte : verdict de chaque script + paramètres d'exécution."""

    decisions: list[FleetDecision]
    max_concurrent: int
    dry_run: bool
    trigger_agents: bool
    generated_at: datetime

    @property
    def to_launch(self) -> list[FleetDecision]:
        return [d for d in self.decisions if d.verdict == "launch"]

    @property
    def skipped(self) -> list[FleetDecision]:
        return [d for d in self.decisions if d.verdict != "launch"]

    def launches_for(self, pole: str) -> list[FleetDecision]:
        return [d for d in self.to_launch if d.pole == pole]

    @property
    def poles_to_launch(self) -> list[str]:
        """Pôles ayant au moins un script à lancer (ordre canonique)."""
        touched = {d.pole for d in self.to_launch}
        return [p for p in POLE_ORDER if p in touched]

    def summary(self) -> str:
        return (
            f"{len(self.to_launch)} script(s) à lancer sur "
            f"{len(self.poles_to_launch)} pôle(s) · {len(self.skipped)} sauté(s) "
            f"({'dry-run' if self.dry_run else 'live'}, max {self.max_concurrent})"
        )


def _decide(
    *,
    cron: str | None,
    runnable: bool,
    frozen: bool,
    breaker_tripped: bool,
    last_run_at: datetime | None,
    runs_done_today: int,
    daily_limit: int | None,
    now: datetime,
    script: str,
) -> tuple[DecisionVerdict, str]:
    """Logique de décision pure (ordre de priorité figé, miroir de l'orchestrateur SRE)."""
    if frozen:
        return "skipped_frozen", "kill-switch actif"
    if breaker_tripped:
        return "skipped_breaker", f"breaker '{script}' armé"
    if not runnable:
        return "skipped_not_runnable", "aucune classe exécutable enregistrée"
    if not cron:
        return "skipped_no_schedule", "aucune cadence cron déclarée"
    if daily_limit is not None and daily_limit > 0 and runs_done_today >= daily_limit:
        return (
            "skipped_daily_limit",
            f"limite quotidienne atteinte ({runs_done_today}/{daily_limit})",
        )
    if not schedule.is_due(cron, last_run=last_run_at, now=now):
        return "skipped_not_due", "pas encore dû"
    if last_run_at is None:
        return "launch", "jamais lancé, dû"
    return "launch", "dû depuis le dernier passage cron"


async def plan_fleet(
    *,
    poles_root: Path = POLES_DIR,
    now: datetime | None = None,
    dry_run: bool = True,
    trigger_agents: bool = True,
    max_concurrent: int | None = None,
) -> FleetPlan:
    """Construit le plan d'exécution de **toute la flotte** (sans rien lancer)."""
    moment = now or datetime.now(UTC)
    settings = load_fleet_config(poles_root=poles_root)
    ks = load_killswitch(poles_root=poles_root)
    tripped = {b.name for b in breakers.list_tripped(poles_root=poles_root)}
    # Lecture **unique** du journal de flotte : on en dérive dernier-run et
    # runs-today de tous les scripts (évite ~1 relecture par script déclaré).
    all_runs = load_fleet_runs(poles_root=poles_root)
    latest = latest_per_pole_script(runs=all_runs)

    decisions: list[FleetDecision] = []
    for cfg in load_all_poles(poles_root=poles_root):
        registry = script_registry(cfg.id)
        for spec in cfg.scripts:
            runnable = spec.id in registry
            last = latest.get((cfg.id, spec.id))
            last_run_at = last.at if last else None
            cron = spec.schedule
            limit = settings.daily_limit(cfg.id, spec.id)
            done_today = runs_today_for(cfg.id, spec.id, now=moment, runs=all_runs)
            verdict, reason = _decide(
                cron=cron,
                runnable=runnable,
                frozen=ks.is_frozen(spec.id),
                breaker_tripped=spec.id in tripped,
                last_run_at=last_run_at,
                runs_done_today=done_today,
                daily_limit=limit,
                now=moment,
                script=spec.id,
            )
            decisions.append(
                FleetDecision(
                    pole=cfg.id,
                    script=spec.id,
                    verdict=verdict,
                    reason=reason,
                    schedule=cron,
                    last_run_at=last_run_at,
                    next_run_at=(
                        schedule.next_run(cron, after=last_run_at or moment) if cron else None
                    ),
                    runs_today=done_today,
                    daily_limit=limit,
                    runnable=runnable,
                )
            )

    # Lancements d'abord, le plus en retard en tête (last_run le plus ancien),
    # puis ordre pôle/script stable.
    pole_rank = {p: i for i, p in enumerate(POLE_ORDER)}
    decisions.sort(
        key=lambda d: (
            d.verdict != "launch",
            d.last_run_at or datetime.min.replace(tzinfo=UTC),
            pole_rank.get(d.pole, 99),
            d.script,
        )
    )
    return FleetPlan(
        decisions=decisions,
        max_concurrent=max_concurrent or settings.max_concurrent,
        dry_run=dry_run,
        trigger_agents=trigger_agents,
        generated_at=moment,
    )


# =============================================================================
# Exécution — cycle complet script → mémoire → agent → action
# =============================================================================
@dataclass(frozen=True)
class ScriptOutcome:
    """Résultat d'exécution d'un script lancé par l'orchestrateur de flotte."""

    pole: str
    script: str
    status: str  # success | failed | skipped
    summary: str | None
    error: str | None


@dataclass(frozen=True)
class AgentOutcome:
    """Résultat du réveil de l'agent d'un pôle (après ses scripts)."""

    pole: str
    agent: str
    status: str  # success | failed | skipped
    summary: str | None
    error: str | None
    actions: int


@dataclass
class FleetCycleResult:
    """Bilan d'un cycle de flotte (scripts + agents)."""

    script_outcomes: list[ScriptOutcome]
    agent_outcomes: list[AgentOutcome]
    dry_run: bool

    def summary(self) -> str:
        ok = sum(1 for o in self.script_outcomes if o.status == "success")
        agents = sum(1 for o in self.agent_outcomes if o.status == "success")
        return (
            f"{len(self.script_outcomes)} script(s) exécuté(s) ({ok} ok) · "
            f"{len(self.agent_outcomes)} agent(s) réveillé(s) ({agents} ok)"
        )


# Runners injectables (tests hermétiques).
ScriptRunner = Callable[[BaseScript], Awaitable[ScriptResult]]
AgentRunner = Callable[[BaseAgent], Awaitable[AgentResult]]


async def _run_and_journal(
    pole: str,
    script: str,
    cls: type[BaseScript],
    *,
    poles_root: Path,
    runner: ScriptRunner,
    now: datetime,
) -> ScriptOutcome:
    """Lance un script et journalise le run dans le **journal de flotte**.

    On écrit dans ``data/poles/fleet_runlog.jsonl`` (et **jamais** dans le runlog
    SRE, réservé au cockpit SRE) pour que le prochain plan voie le dernier passage
    de ce couple ``(pole, script)`` — base de la cadence cron et du ``daily_limit``.
    Les scripts SRE continuent en plus de se journaliser dans leur propre runlog
    via ``run_sre_script`` (deux journaux, deux consommateurs distincts).

    Un runner qui **lève** (cas possible seulement via un runner injecté non
    standard — le ``run_script`` par défaut capture déjà tout) est contenu ici :
    on journalise un run ``failed`` et on renvoie un ``ScriptOutcome`` failed,
    sans casser le cycle (même invariant que :func:`_wake_agent`).
    """
    started = time.monotonic()
    try:
        result = await runner(cls(poles_root=poles_root))
    except Exception as exc:  # un script qui crashe ne casse pas le cycle de flotte
        duration_ms = (time.monotonic() - started) * 1000.0
        logger.exception(f"fleet — script {pole}/{script} en échec")
        error = f"{type(exc).__name__}: {exc}"
        append_fleet_run(
            FleetRun(
                at=now,
                pole=pole,
                script=script,
                status="failed",
                duration_ms=duration_ms,
                summary=f"exception : {type(exc).__name__}",
                error=error,
            ),
            poles_root=poles_root,
        )
        return ScriptOutcome(pole=pole, script=script, status="failed", summary=None, error=error)

    duration_ms = (time.monotonic() - started) * 1000.0
    append_fleet_run(
        FleetRun(
            at=now,
            pole=pole,
            script=script,
            status=result.status,
            duration_ms=duration_ms,
            summary=result.summary or "",
            error=result.error,
        ),
        poles_root=poles_root,
    )
    return ScriptOutcome(
        pole=pole, script=script, status=result.status, summary=result.summary, error=result.error
    )


async def _launch_pole_scripts(
    pole: str,
    decisions: list[FleetDecision],
    *,
    poles_root: Path,
    runner: ScriptRunner,
    sem: asyncio.Semaphore,
    now: datetime,
) -> list[ScriptOutcome]:
    """Lance (sous sémaphore) les scripts dûs d'un pôle et renvoie leurs résultats."""
    registry_map = script_registry(pole)

    async def _one(decision: FleetDecision) -> ScriptOutcome:
        cls = registry_map.get(decision.script)
        if cls is None:  # garde-fou : plan / registre incohérents
            return ScriptOutcome(
                pole=decision.pole,
                script=decision.script,
                status="skipped",
                summary="aucune classe exécutable enregistrée",
                error=None,
            )
        async with sem:
            return await _run_and_journal(
                decision.pole, decision.script, cls, poles_root=poles_root, runner=runner, now=now
            )

    return list(await asyncio.gather(*(_one(d) for d in decisions)))


async def run_fleet_cycle(
    plan: FleetPlan,
    *,
    poles_root: Path = POLES_DIR,
    script_runner: ScriptRunner | None = None,
    agent_runner: AgentRunner | None = None,
    now: datetime | None = None,
) -> FleetCycleResult:
    """Exécute le plan (sauf dry-run) : scripts dûs par pôle, puis réveil de l'agent.

    Pour chaque pôle (ordre canonique) : on lance ses scripts dûs (capés par un
    sémaphore), puis — si le pôle a un agent déclenché par ``cron`` et qu'au moins
    un script a tourné — on **réveille l'agent** qui relit la mémoire fraîche et
    agit. L'agent Mémoire (``trigger: script``) et le pôle SRE (sans agent) ne
    sont jamais réveillés ici.
    """
    if plan.dry_run:
        logger.info(f"fleet — dry-run : {plan.summary()}")
        return FleetCycleResult(script_outcomes=[], agent_outcomes=[], dry_run=True)

    moment = now or datetime.now(UTC)
    run_s = script_runner or run_script
    run_a = agent_runner or _default_agent_runner
    sem = asyncio.Semaphore(max(1, plan.max_concurrent))
    triggers = {
        cfg.id: (cfg.agent.trigger if cfg.agent else None)
        for cfg in load_all_poles(poles_root=poles_root)
    }

    script_outcomes: list[ScriptOutcome] = []
    agent_outcomes: list[AgentOutcome] = []

    for pole in plan.poles_to_launch:
        pole_outcomes = await _launch_pole_scripts(
            pole, plan.launches_for(pole), poles_root=poles_root, runner=run_s, sem=sem, now=moment
        )
        script_outcomes.extend(pole_outcomes)

        # Réveil de l'agent : seulement si pôle 1-6 (trigger cron) et ≥1 script tourné.
        ran = any(o.status != "skipped" for o in pole_outcomes)
        agent_cls = agent_class(pole)
        if plan.trigger_agents and ran and agent_cls is not None and triggers.get(pole) == "cron":
            agent_outcomes.append(
                await _wake_agent(pole, agent_cls, poles_root=poles_root, runner=run_a)
            )

    logger.info(
        f"fleet — live : {len(script_outcomes)} script(s), {len(agent_outcomes)} agent(s) réveillé(s)"
    )
    return FleetCycleResult(
        script_outcomes=script_outcomes, agent_outcomes=agent_outcomes, dry_run=False
    )


async def _default_agent_runner(agent: BaseAgent) -> AgentResult:
    """Runner d'agent par défaut : ``agent.run()`` (charge la mémoire puis ``act``)."""
    return await agent.run()


async def _wake_agent(
    pole: str,
    agent_cls: type[BaseAgent],
    *,
    poles_root: Path,
    runner: AgentRunner,
) -> AgentOutcome:
    """Réveille l'agent d'un pôle, en convertissant toute exception en échec."""
    try:
        result = await runner(agent_cls(poles_root=poles_root))
    except Exception as exc:  # un agent qui crashe ne casse pas le cycle de flotte
        logger.exception(f"fleet — agent {pole} en échec")
        return AgentOutcome(
            pole=pole,
            agent=agent_cls.__name__,
            status="failed",
            summary=None,
            error=f"{type(exc).__name__}: {exc}",
            actions=0,
        )
    return AgentOutcome(
        pole=pole,
        agent=agent_cls.__name__,
        status=result.status,
        summary=result.summary,
        error=result.error,
        actions=len(result.actions),
    )


__all__ = [
    "DEFAULT_MAX_CONCURRENT",
    "FLEET_CONFIG_FILE",
    "AgentOutcome",
    "AgentRunner",
    "DecisionVerdict",
    "FleetConfig",
    "FleetCycleResult",
    "FleetDecision",
    "FleetPlan",
    "ScriptOutcome",
    "ScriptRunner",
    "fleet_config_path",
    "load_fleet_config",
    "plan_fleet",
    "run_fleet_cycle",
]
