"""``MarketingAgent`` — le cerveau du pôle Marketing (archi v2, S2).

Le pôle Marketing est **en aval** de la Veille : son agent lit sa propre mémoire
(publications, engagement, médias écrits par ses scripts) **plus la mémoire de la
Veille en cross-pôle** (``reads_cross_pole: [veille]`` dans ``pole.yaml``), puis
**synthétise des recommandations de contenu** routées par canal
(:func:`~argos_ops.poles.marketing.editorial.plan_editorial`). Il dispose d'une
**banque de skills** (6 writers + SEO brief / newsletter / reply / editorial /
brand-check / KB updater) — ce ne sont plus des bots
(:mod:`~argos_ops.poles.marketing.skills`).

Sous D-017 le cerveau réel serait ``claude -p`` (flag ``OPS_BRAIN_ENABLED``) qui
*rédige* les drafts via ces skills, avec **fallback heuristique obligatoire** :
ici le socle se contente de la planification heuristique pure (testable
hors-ligne). Brancher le cerveau = surcharger :meth:`_plan` sans toucher au reste.
"""

from __future__ import annotations

from argos_ops.poles.agent import AgentContext, AgentResult, BaseAgent
from argos_ops.poles.marketing.editorial import Recommendation, plan_editorial
from argos_ops.poles.memory import MemoryRecord


class MarketingAgent(BaseAgent):
    """Synthétise Veille + mémoire propre en recommandations de contenu routées."""

    pole = "marketing"
    name = "MarketingAgent"

    def _plan(self, records: list[MemoryRecord]) -> list[Recommendation]:
        """Point d'extension du cerveau (D-017). Défaut = heuristique pure."""
        return plan_editorial(records)

    async def act(self, context: AgentContext) -> AgentResult:
        # Le marketing voit sa mémoire propre + celle de la Veille (cross-pôle).
        records = context.all_records()
        if not records:
            return AgentResult(
                status="skipped",
                summary="Aucune mémoire (propre ni Veille) — rien à mettre en récit.",
            )

        recommendations = self._plan(records)
        if not recommendations:
            return AgentResult(
                status="skipped",
                summary=(
                    f"{len(records)} fait(s) visible(s) mais aucun signal éditorialisable "
                    "(pas de tendance / concurrent / menace / presse à valoriser)."
                ),
            )

        actions = [
            f"[{rec.severity}] {rec.angle} → {', '.join(rec.channels) or 'aucun canal'} "
            f"({rec.kind})"
            for rec in recommendations
        ]
        critical = sum(1 for r in recommendations if r.severity == "critical")
        veille_seen = "veille" in context.cross_pole
        summary = (
            f"{len(recommendations)} recommandation(s) de contenu depuis {len(records)} fait(s)"
            f"{' (Veille incluse)' if veille_seen else ''} — {critical} critique(s)"
        )
        return AgentResult(status="success", summary=summary, actions=actions)


__all__ = ["MarketingAgent"]
