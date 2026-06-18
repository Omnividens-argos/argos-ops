"""``OrchestratorBot`` — chef de fleet déterministe du pôle SRE (archi v2, S8).

Malgré son nom historique, ce n'est **pas** un agent LLM : c'est un planificateur
pur qui décide quels scripts SRE doivent tourner *maintenant*, à partir de :

- la **cadence cron** déclarée dans ``pole.yaml`` (:mod:`argos_ops.poles.sre.schedule`) ;
- le **kill-switch** (un script gelé est sauté) ;
- les **breakers** (un script dont le breaker éponyme est armé est sauté) ;
- une **limite quotidienne** par script (``data/poles/sre/orchestrator.yaml``),
  comptée sur le runlog.

Mode **dry-run** par défaut (logue le plan, ne lance rien). En mode live, exécute
les scripts dûs via un sémaphore (``max_concurrent``, 2 par défaut). Réutilise le
``run_script`` du socle (qui passe par ``run_sre_script`` : kill-switch + journal).
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

import yaml
from loguru import logger

from argos_ops.poles.base import BaseScript, ScriptResult, run_script
from argos_ops.poles.config import POLES_DIR, load_pole_config
from argos_ops.poles.sre import breakers, schedule
from argos_ops.poles.sre.killswitch import load_killswitch
from argos_ops.poles.sre.runlog import latest_per_script, runs_today
from argos_ops.poles.sre.scripts import RUNNABLE

SRE_POLE = "sre"
ORCHESTRATOR_FILE = "orchestrator.yaml"
DEFAULT_MAX_CONCURRENT = 2

DecisionVerdict = Literal[
    "launch",
    "skipped_frozen",
    "skipped_breaker",
    "skipped_not_due",
    "skipped_daily_limit",
    "skipped_no_schedule",
]


def orchestrator_config_path(*, poles_root: Path = POLES_DIR) -> Path:
    return poles_root / SRE_POLE / ORCHESTRATOR_FILE


@dataclass(frozen=True)
class OrchestratorConfig:
    """Réglages runtime de l'orchestrateur."""

    max_concurrent: int = DEFAULT_MAX_CONCURRENT
    daily_limits: dict[str, int] = field(default_factory=dict)


def load_orchestrator_config(*, poles_root: Path = POLES_DIR) -> OrchestratorConfig:
    path = orchestrator_config_path(poles_root=poles_root)
    if not path.exists():
        return OrchestratorConfig()
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        logger.warning(f"sre.orchestrator — config invalide, défauts : {exc}")
        return OrchestratorConfig()
    if not isinstance(raw, dict):
        return OrchestratorConfig()
    limits_raw = raw.get("daily_limits")
    limits: dict[str, int] = {}
    if isinstance(limits_raw, dict):
        for k, v in limits_raw.items():
            try:
                limits[str(k)] = int(v)
            except (ValueError, TypeError):
                continue
    raw_mc = raw.get("max_concurrent")
    try:
        # ``0`` est une valeur explicite (à clamper à 1), pas un « non défini » :
        # ne pas utiliser ``or`` qui retomberait sur le défaut.
        max_concurrent = DEFAULT_MAX_CONCURRENT if raw_mc is None else int(raw_mc)
    except (ValueError, TypeError):
        max_concurrent = DEFAULT_MAX_CONCURRENT
    return OrchestratorConfig(max_concurrent=max(1, max_concurrent), daily_limits=limits)


@dataclass(frozen=True)
class ScriptDecision:
    """Verdict de l'orchestrateur pour un script."""

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
class OrchestrationPlan:
    """Plan complet : verdict de chaque script + paramètres d'exécution."""

    decisions: list[ScriptDecision]
    max_concurrent: int
    dry_run: bool
    generated_at: datetime

    @property
    def to_launch(self) -> list[ScriptDecision]:
        return [d for d in self.decisions if d.verdict == "launch"]

    @property
    def skipped(self) -> list[ScriptDecision]:
        return [d for d in self.decisions if d.verdict != "launch"]

    def summary(self) -> str:
        return (
            f"{len(self.to_launch)} à lancer · {len(self.skipped)} sauté(s) "
            f"({'dry-run' if self.dry_run else 'live'}, max {self.max_concurrent})"
        )


@dataclass(frozen=True)
class ExecutionOutcome:
    """Résultat d'exécution d'un script lancé par l'orchestrateur."""

    script: str
    status: str  # success | failed | skipped
    summary: str | None
    error: str | None


def _decide(
    *,
    script: str,
    cron: str | None,
    last_run_at: datetime | None,
    next_run_at: datetime | None,
    frozen: bool,
    breaker_tripped: bool,
    runs_done_today: int,
    daily_limit: int | None,
    now: datetime,
) -> tuple[DecisionVerdict, str]:
    """Logique de décision pure (ordre de priorité figé)."""
    if frozen:
        return "skipped_frozen", "kill-switch actif"
    if breaker_tripped:
        return "skipped_breaker", f"breaker '{script}' armé"
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


async def plan_execution(
    *,
    poles_root: Path = POLES_DIR,
    now: datetime | None = None,
    dry_run: bool = True,
    max_concurrent: int | None = None,
) -> OrchestrationPlan:
    """Construit le plan d'exécution des scripts SRE (sans rien lancer)."""
    moment = now or datetime.now(UTC)
    config = load_pole_config(SRE_POLE, poles_root=poles_root)
    settings = load_orchestrator_config(poles_root=poles_root)
    ks = load_killswitch(poles_root=poles_root)
    tripped = {b.name for b in breakers.list_tripped(poles_root=poles_root)}
    latest = latest_per_script(poles_root=poles_root)

    decisions: list[ScriptDecision] = []
    for spec in config.scripts:
        last = latest.get(spec.id)
        last_run_at = last.at if last else None
        cron = spec.schedule
        daily_limit = settings.daily_limits.get(spec.id)
        done_today = runs_today(spec.id, now=moment, poles_root=poles_root)
        verdict, reason = _decide(
            script=spec.id,
            cron=cron,
            last_run_at=last_run_at,
            next_run_at=schedule.next_run(cron, after=last_run_at or moment) if cron else None,
            frozen=ks.is_frozen(spec.id),
            breaker_tripped=spec.id in tripped,
            runs_done_today=done_today,
            daily_limit=daily_limit,
            now=moment,
        )
        decisions.append(
            ScriptDecision(
                pole=SRE_POLE,
                script=spec.id,
                verdict=verdict,
                reason=reason,
                schedule=cron,
                last_run_at=last_run_at,
                next_run_at=schedule.next_run(cron, after=last_run_at or moment) if cron else None,
                runs_today=done_today,
                daily_limit=daily_limit,
                runnable=spec.id in RUNNABLE,
            )
        )

    # Les lancements d'abord, le plus en retard en tête (last_run le plus ancien).
    decisions.sort(
        key=lambda d: (
            d.verdict != "launch",
            d.last_run_at or datetime.min.replace(tzinfo=UTC),
            d.script,
        )
    )
    return OrchestrationPlan(
        decisions=decisions,
        max_concurrent=max_concurrent or settings.max_concurrent,
        dry_run=dry_run,
        generated_at=moment,
    )


# runner : exécute un script et renvoie son ``ScriptResult`` (injectable en test).
Runner = Callable[[BaseScript], Awaitable[ScriptResult]]


async def execute_plan(
    plan: OrchestrationPlan, *, poles_root: Path = POLES_DIR, runner: Runner | None = None
) -> list[ExecutionOutcome]:
    """Exécute les scripts dûs (sauf dry-run), capés par un sémaphore."""
    if plan.dry_run:
        logger.info(f"sre.orchestrator — dry-run : {plan.summary()}")
        return []
    run = runner or run_script
    sem = asyncio.Semaphore(max(1, plan.max_concurrent))

    async def _run_one(decision: ScriptDecision) -> ExecutionOutcome:
        cls = RUNNABLE.get(decision.script)
        if cls is None:
            return ExecutionOutcome(decision.script, "skipped", "aucun runner enregistré", None)
        async with sem:
            result = await run(cls(poles_root=poles_root))
        return ExecutionOutcome(decision.script, result.status, result.summary, result.error)

    outcomes = await asyncio.gather(*(_run_one(d) for d in plan.to_launch))
    logger.info(f"sre.orchestrator — live : {len(outcomes)} script(s) exécuté(s)")
    return list(outcomes)


__all__ = [
    "DEFAULT_MAX_CONCURRENT",
    "DecisionVerdict",
    "ExecutionOutcome",
    "OrchestrationPlan",
    "OrchestratorConfig",
    "Runner",
    "ScriptDecision",
    "execute_plan",
    "load_orchestrator_config",
    "orchestrator_config_path",
    "plan_execution",
]
