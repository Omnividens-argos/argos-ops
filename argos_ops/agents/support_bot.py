"""SupportBot — Support Tier 1 (P22.G — health-check passif).

Le RAG interactif Tier 1 se fait via le slash ``/run-support-tier1`` qui
invoque le skill ``kb-rag`` (P6) en humain-in-the-loop. L'agent Python
ne fait donc qu'un **health-check passif** : il compte les chunks KB
indexés pour exposer un état au panel Admin et à BotHealthBot.

Pattern identique à :class:`argos_ops.agents.seo_bot.SEOBot` et
:class:`argos_ops.agents.decision_logger.DecisionLogger` :
- ``run()`` retourne un snapshot read-only (nombre de chunks, dernier
  chunk indexé)
- Le drafting / réponse RAG reste 100 % côté slash command

Garde-fou anti-hallucination : si la KB est vide (0 chunks), le run
retourne ``failed`` pour alerter Discord (le slash ne pourrait pas
répondre à un ticket support sans contexte).

Cf. plan ``docs/ARGOS_OPS_PLAN.md`` Annexe D § 5 Customer Success.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func, select

from argos_ops.agents.base import BaseAgent, IOItem, RunResult
from argos_ops.crm.db import session_scope
from argos_ops.crm.models import KBChunk
from argos_ops.exceptions import AgentDataSourceError


class SupportBot(BaseAgent):
    """Support Tier 1 — health-check de la KB Argos."""

    name = "SupportBot"
    command = "/run-support-tier1"
    breaker_name = None
    ai_act_risk_class = "limited"

    async def run(self) -> RunResult:
        """Compte les chunks KB indexés.

        Le drafting réel est fait par le slash ``/run-support-tier1``
        en humain-in-the-loop, pas par cette méthode.
        """
        try:
            async with session_scope() as session:
                result = await session.execute(
                    select(func.count()).select_from(KBChunk)
                )
                count = int(result.scalar() or 0)
        except Exception as exc:
            raise AgentDataSourceError(f"count kb_chunks: {exc}") from exc

        if count == 0:
            return RunResult(
                status="failed",
                error=(
                    "KB vide — SupportBot ne peut pas répondre Tier 1. "
                    "Relance `uv run python scripts/seed_kb.py`."
                ),
                extras={"kb_chunks": 0},
            )

        return RunResult(
            status="success",
            output_summary=f"{count} chunks KB indexés",
            inputs=[
                IOItem(
                    label="Knowledge Base Argos (chunks indexés)",
                    kind="kb",
                    detail="table kb_chunks (pgvector) — disponibilité RAG Tier 1",
                    count=count,
                )
            ],
            extras={
                "kb_chunks": count,
                "checked_at": datetime.now(UTC).isoformat(),
            },
        )


__all__ = ["SupportBot"]
