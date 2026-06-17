"""``PubAgent`` — le cerveau du pôle Pub (archi v2, S3).

Le pôle Pub est **en aval** de la Veille (tendances / pricing), du Marketing
(ton / mots-clés) et de la Finance (budget). Son agent lit sa propre mémoire
(recos chiffrées écrites par ``ads_optimizer``, actions shadow d'``ad_bot``)
**plus** la mémoire de ces pôles en cross-pôle (``reads_cross_pole`` dans
``pole.yaml`` ; Finance lue **défensivement** — absente tant qu'elle n'a pas de
mémoire), puis **synthétise un plan d'actions**
(:func:`~argos_ops.poles.pub.plan.plan_actions`) : idées de créa issues de la
Veille + actions budget issues de l'optimiseur.

**Garde-fou central** : avant de planifier, l'agent lit l'état du breaker
``ad_spend_runaway`` (:mod:`~argos_ops.poles.pub.budget`, donnée déterministe de
son propre pôle, écrite par son script) et **gèle** les actions augmentatrices de
dépense s'il est armé. « Le LLM propose, Python tranche » : sous D-017 le cerveau
réel (``claude -p``) surchargerait :meth:`_plan` pour affiner les angles, mais ne
peut jamais lever ce gel. Le fallback heuristique reste :func:`plan_actions`.
"""

from __future__ import annotations

from argos_ops.poles.agent import AgentContext, AgentResult, BaseAgent
from argos_ops.poles.memory import MemoryRecord
from argos_ops.poles.pub import budget
from argos_ops.poles.pub.plan import AdPlan, plan_actions


class PubAgent(BaseAgent):
    """Synthétise Veille/Marketing + recos propres en plan d'actions borné par le breaker."""

    pole = "pub"
    name = "PubAgent"

    def _plan(self, records: list[MemoryRecord], *, breaker_tripped: bool) -> list[AdPlan]:
        """Point d'extension du cerveau (D-017). Défaut = heuristique pure."""
        return plan_actions(records, breaker_tripped=breaker_tripped)

    async def act(self, context: AgentContext) -> AgentResult:
        # Garde-fou Python : l'état du breaker borne le plan AVANT toute décision.
        state = budget.load_budget(poles_root=self.poles_root)
        records = context.all_records()
        if not records:
            return AgentResult(
                status="skipped",
                summary="Aucune mémoire (propre ni cross-pôle) — rien à planifier.",
            )

        plans = self._plan(records, breaker_tripped=state.breaker_tripped)
        if not plans:
            return AgentResult(
                status="skipped",
                summary=(
                    f"{len(records)} fait(s) visible(s) mais aucun signal actionnable "
                    "(ni reco budget, ni sujet Veille à transformer en campagne)."
                ),
            )

        actions = [
            f"[{p.severity}] {p.action} → {', '.join(p.platforms) or 'toutes plateformes'} "
            f"({p.kind}){' [GELÉ breaker]' if p.suppressed_by_breaker else ''}"
            for p in plans
        ]
        suppressed = sum(1 for p in plans if p.suppressed_by_breaker)
        critical = sum(1 for p in plans if p.severity == "critical")
        seen = [p for p in ("veille", "marketing", "finance") if p in context.cross_pole]
        cross_note = f" (cross-pôle : {', '.join(seen)})" if seen else ""
        breaker_note = (
            f" — breaker ARMÉ, {suppressed} action(s) gelée(s)" if state.breaker_tripped else ""
        )
        summary = (
            f"{len(plans)} action(s) planifiée(s) depuis {len(records)} fait(s)"
            f"{cross_note} — {critical} critique(s){breaker_note}"
        )
        return AgentResult(status="success", summary=summary, actions=actions)


__all__ = ["PubAgent"]
