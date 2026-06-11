"""Classe de base partagée par tous les agents Argos Ops.

Pattern :
- L'agent contient la logique métier dans ``async def run(self) -> RunResult``
- :func:`run_agent` enrobe l'agent : check runtime (P16.B) → start_agent_run →
  appel ``run()`` → complete_agent_run avec status final → log loguru
- Le check runtime applique dans l'ordre : breaker tripped > disabled
  (Admin Panel toggle OFF) > paused_until (pause temporaire) >
  daily_limit (quota journalier). Géré par ``argos_ops.agent_runtime``.
- Les agents ne touchent pas à la DB d'observabilité (agent_runs) eux-mêmes :
  c'est :func:`run_agent` qui s'en charge, pour éviter la duplication
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from typing import Literal

from loguru import logger

from argos_ops import fleet_memory
from argos_ops.agent_runtime import check_runtime_state
from argos_ops.crm.db import session_scope
from argos_ops.crm.repository import complete_agent_run, start_agent_run

RunStatus = Literal[
    "success",
    "failed",
    "killed_by_breaker",
    "skipped_disabled",
    "skipped_paused",
    "skipped_daily_limit",
]


@dataclass
class IOItem:
    """Une entrée (IN) ou sortie (OUT) structurée d'un run d'agent.

    Sert à afficher dans le cockpit « ce que le bot a regardé » (IN) →
    « ce qu'il a trouvé / produit » (OUT). Renseigné par l'agent dans son
    :class:`RunResult` ; sérialisé en JSONB dans ``agent_runs.inputs`` /
    ``agent_runs.outputs``. Tout est optionnel sauf ``label`` — un bot non
    instrumenté laisse les listes vides et l'UI retombe sur une vue dérivée.
    """

    label: str  # ex. "Boîte IMAP contact@omnividens.fr", "KPIs Postgres"
    kind: str = "other"  # imap|db|file|kb|memory|api|http|draft|discord|email|other
    detail: str | None = None  # ex. "50 mails non lus", "data/uptime/endpoints.yaml"
    ref: str | None = None  # chemin fichier ou URL cliquable (optionnel)
    count: int | None = None  # cardinalité (ex. 50)


@dataclass
class RunResult:
    """Résultat d'exécution d'un agent — sérialisé dans ``agent_runs``."""

    status: RunStatus
    output_summary: str | None = None
    error: str | None = None
    inputs: list[IOItem] = field(default_factory=list)
    outputs: list[IOItem] = field(default_factory=list)
    extras: dict[str, object] = field(default_factory=dict)


class BaseAgent(ABC):
    """Tout agent Argos Ops hérite de cette classe."""

    name: str  # ex : "DigestBuilder", "EmailBot"
    breaker_name: str | None = None  # nom du breaker à checker (None = pas de breaker)
    command: str | None = None  # ex : "/morning-digest" — loggé dans agent_runs.command

    @abstractmethod
    async def run(self) -> RunResult:
        """Logique métier — doit être idempotent en cas de retry."""


async def run_agent(agent: BaseAgent) -> RunResult:
    """Enrobe l'exécution d'un agent : runtime checks → log start → run → log end.

    Runtime checks (P16.B) — l'agent est court-circuité avec un status
    explicite si :
    - le breaker associé est tripped → ``killed_by_breaker``
    - l'agent est désactivé via l'Admin Panel → ``skipped_disabled``
    - une pause temporaire est active → ``skipped_paused``
    - le ``daily_limit`` du jour est atteint → ``skipped_daily_limit``

    Garantit qu'une ligne est insérée dans ``agent_runs`` à chaque
    tentative, même skip ou crash. Permet l'audit complet depuis le
    dashboard.
    """
    logger.info(f"Agent {agent.name} — start")
    decision = await check_runtime_state(agent.name, breaker_name=agent.breaker_name)
    if decision.verdict != "allowed":
        async with session_scope() as session:
            run = await start_agent_run(session, agent_name=agent.name, command=agent.command)
            await complete_agent_run(
                session,
                run.id or 0,
                status=decision.verdict,
                error=decision.reason,
            )
        logger.warning(f"Agent {agent.name} — {decision.verdict} ({decision.reason})")
        return RunResult(status=decision.verdict, error=decision.reason)

    async with session_scope() as session:
        run = await start_agent_run(session, agent_name=agent.name, command=agent.command)
        run_id = run.id or 0

    try:
        result = await agent.run()
    except Exception as exc:  # top-level catch pour logger en DB avant remontée
        logger.exception(f"Agent {agent.name} — failed")
        async with session_scope() as session:
            await complete_agent_run(
                session,
                run_id,
                status="failed",
                error=f"{type(exc).__name__}: {exc}",
            )
        return RunResult(status="failed", error=f"{type(exc).__name__}: {exc}")

    async with session_scope() as session:
        await complete_agent_run(
            session,
            run_id,
            status=result.status,
            output_summary=result.output_summary,
            error=result.error,
            inputs=[asdict(i) for i in result.inputs] or None,
            outputs=[asdict(o) for o in result.outputs] or None,
        )
    if result.status == "success":
        await _remember_run_facts(agent, result, run_id=run_id)
    logger.success(f"Agent {agent.name} — {result.status}")
    return result


async def _remember_run_facts(agent: BaseAgent, result: RunResult, *, run_id: int = 0) -> None:
    """Conserve dans la mémoire de flotte ce que le bot a décidé de retenir.

    Le bot expose ses souvenirs via ``RunResult.extras["fleet_facts"]`` (liste
    de :class:`argos_ops.fleet_memory.FactDraft`). Chaque fait est tracé vers
    son run d'origine (``run_id`` + source ``run#N (commande)``) — c'est ce qui
    permet au cockpit de remonter d'un souvenir au travail (IN → OUT) qui l'a
    produit. La mémoire ne doit JAMAIS faire échouer un run : toute erreur est
    logguée puis avalée.
    """
    raw = result.extras.get("fleet_facts")
    if not raw:
        return
    if not isinstance(raw, list):
        logger.warning(f"Agent {agent.name} — extras['fleet_facts'] n'est pas une liste, ignoré")
        return
    command = agent.command or agent.name
    source = f"run#{run_id} ({command})" if run_id else command
    try:
        stored = await fleet_memory.remember(
            agent.name, raw, default_source=source, run_id=run_id or None
        )
        if stored:
            logger.info(f"Agent {agent.name} — {len(stored)} fait(s) mémorisé(s)")
    except Exception as exc:  # la mémoire ne doit jamais faire échouer un run
        logger.warning(f"Agent {agent.name} — conservation mémoire échouée : {exc}")


__all__ = ["BaseAgent", "RunResult", "RunStatus", "run_agent"]
