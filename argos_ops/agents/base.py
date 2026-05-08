"""Classe de base partagée par tous les agents Argos Ops.

Pattern :
- L'agent contient la logique métier dans ``async def run(self) -> RunResult``
- :func:`run_agent` enrobe l'agent : check breaker → start_agent_run →
  appel ``run()`` → complete_agent_run avec status final → log loguru
- Les agents ne touchent pas à la DB d'observabilité (agent_runs) eux-mêmes :
  c'est :func:`run_agent` qui s'en charge, pour éviter la duplication
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Literal

from loguru import logger

from argos_ops.crm.db import session_scope
from argos_ops.crm.repository import (
    complete_agent_run,
    is_breaker_tripped,
    start_agent_run,
)

RunStatus = Literal["success", "failed", "killed_by_breaker"]


@dataclass
class RunResult:
    """Résultat d'exécution d'un agent — sérialisé dans ``agent_runs``."""

    status: RunStatus
    output_summary: str | None = None
    error: str | None = None
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
    """Enrobe l'exécution d'un agent : breaker → log start → run → log end.

    Garantit qu'une ligne est insérée dans ``agent_runs`` à chaque tentative,
    même si l'agent crash (status="failed" + error) ou est court-circuité par
    un breaker (status="killed_by_breaker").
    """
    logger.info(f"Agent {agent.name} — start")
    async with session_scope() as session:
        if agent.breaker_name is not None and await is_breaker_tripped(session, agent.breaker_name):
            run = await start_agent_run(session, agent_name=agent.name, command=agent.command)
            await complete_agent_run(
                session,
                run.id or 0,
                status="killed_by_breaker",
                error=f"breaker '{agent.breaker_name}' tripped",
            )
            logger.warning(f"Agent {agent.name} — killed_by_breaker '{agent.breaker_name}'")
            return RunResult(
                status="killed_by_breaker", error=f"breaker '{agent.breaker_name}' tripped"
            )
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
        )
    logger.success(f"Agent {agent.name} — {result.status}")
    return result


__all__ = ["BaseAgent", "RunResult", "RunStatus", "run_agent"]
