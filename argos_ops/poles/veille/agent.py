"""``VeilleAgent`` — le cerveau du pôle Veille (archi v2, S1).

Le pôle Veille est **en amont** de la flotte : ses scripts (TrendSpotter,
CompetitorWatcher, BreachWatcher, …) écrivent des signaux bruts dans leur
mémoire ; le ``VeilleAgent`` les **synthétise en insights actionnables** et les
**route** vers les pôles aval (Marketing / Pub / Vente). Il ne lit aucun autre
pôle (``reads_cross_pole: []`` dans ``pole.yaml``) — la veille n'a pas besoin du
reste pour qualifier le terrain.

Sous D-017 le cerveau réel serait ``claude -p`` (flag ``OPS_BRAIN_ENABLED``),
avec **fallback heuristique obligatoire** : ici le socle se contente de la
synthèse heuristique pure (:func:`~argos_ops.poles.veille.insights.synthesize_insights`),
ce qui garde l'agent testable hors-ligne. Brancher le cerveau = surcharger
:meth:`_synthesize` sans toucher au reste.
"""

from __future__ import annotations

from argos_ops.poles.agent import AgentContext, AgentResult, BaseAgent
from argos_ops.poles.memory import MemoryRecord
from argos_ops.poles.veille.insights import Insight, synthesize_insights


class VeilleAgent(BaseAgent):
    """Synthétise la mémoire des scripts de veille en insights routés."""

    pole = "veille"
    name = "VeilleAgent"

    def _synthesize(self, records: list[MemoryRecord]) -> list[Insight]:
        """Point d'extension du cerveau (D-017). Défaut = heuristique pure."""
        return synthesize_insights(records)

    async def act(self, context: AgentContext) -> AgentResult:
        # Veille n'a pas de cross-pôle : on ne regarde que sa propre mémoire.
        records: list[MemoryRecord] = []
        for script_records in context.own.values():
            records.extend(script_records)

        if not records:
            return AgentResult(
                status="skipped",
                summary="Aucun signal de veille en mémoire — rien à synthétiser.",
            )

        insights = self._synthesize(records)
        actions = [
            f"[{insight.severity}] {insight.title} → "
            f"{', '.join(insight.suggested_poles) or 'aucun pôle aval'}"
            for insight in insights
        ]
        critical = sum(1 for i in insights if i.severity == "critical")
        summary = (
            f"{len(insights)} insight(s) synthétisé(s) depuis {len(records)} signal(aux) "
            f"({critical} critique[s])"
        )
        return AgentResult(status="success", summary=summary, actions=actions)


__all__ = ["VeilleAgent"]
