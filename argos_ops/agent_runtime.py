"""Runtime guard appelé par ``BaseAgent.run_agent`` avant chaque exécution.

Ce module centralise les checks que le fondateur peut piloter depuis
l'Admin Control Panel (P16.B) :

- ``enabled`` — toggle ON/OFF global de l'agent
- ``paused_until`` — pause temporaire (1h, 24h, ou date custom)
- ``daily_limit`` — N actions max par jour (compte ``agent_runs`` du jour)
- ``breaker_tripped`` — kill switch P15 (déjà géré historiquement par
  ``BaseAgent`` mais consolidé ici pour avoir un seul point de check)

Plan original : Partie 16.1 de ``docs/ARGOS_OPS_PLAN.md``. ``max_tokens_per_day``
n'est pas appliqué tant que le tracking de coût en DB n'est pas câblé
(les agents Sprint 1 n'écrivent pas dans ``agent_runs.cost_estimate_eur``).
À activer en P19 maintenance + tracking tokens Claude Code Pro Max.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from argos_ops.crm.db import session_scope
from argos_ops.crm.repository import (
    count_runs_today,
    get_agent_config,
    is_breaker_tripped,
)

RuntimeVerdict = Literal[
    "allowed",
    "skipped_disabled",
    "skipped_paused",
    "skipped_daily_limit",
    "killed_by_breaker",
]


@dataclass(frozen=True)
class RuntimeDecision:
    """Verdict du runtime + raison lisible (loggée dans ``agent_runs.error``)."""

    verdict: RuntimeVerdict
    reason: str


async def check_runtime_state(
    agent_name: str, *, breaker_name: str | None = None
) -> RuntimeDecision:
    """Effectue tous les checks runtime dans l'ordre de priorité.

    Ordre :
    1. **Breaker tripped** — priorité max, court-circuite tout
    2. **Disabled** — l'agent est désactivé via le panel
    3. **Paused** — pause temporaire active (``paused_until > now``)
    4. **Daily limit** — quota journalier atteint

    Si tout passe, renvoie ``verdict='allowed'``.
    """
    async with session_scope() as session:
        # 1. Breaker — priorité absolue
        if breaker_name is not None and await is_breaker_tripped(session, breaker_name):
            return RuntimeDecision(
                verdict="killed_by_breaker",
                reason=f"breaker '{breaker_name}' tripped",
            )

        config = await get_agent_config(session, agent_name)

        # 2. Disabled
        if not config.enabled:
            return RuntimeDecision(
                verdict="skipped_disabled",
                reason="agent disabled via Admin Panel",
            )

        # 3. Paused
        now = datetime.now(UTC)
        if config.paused_until is not None and config.paused_until > now:
            return RuntimeDecision(
                verdict="skipped_paused",
                reason=f"paused until {config.paused_until.isoformat()}",
            )

        # 4. Daily limit
        if config.daily_limit is not None and config.daily_limit > 0:
            count = await count_runs_today(session, agent_name)
            if count >= config.daily_limit:
                return RuntimeDecision(
                    verdict="skipped_daily_limit",
                    reason=f"daily_limit reached ({count}/{config.daily_limit})",
                )

        return RuntimeDecision(verdict="allowed", reason="ok")


__all__ = ["RuntimeDecision", "RuntimeVerdict", "check_runtime_state"]
