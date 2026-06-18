"""``ExampleAgent`` — cerveau de démonstration (pôle ``_example``).

Gabarit minimal d'un :class:`~argos_ops.poles.agent.BaseAgent` : il charge son
contexte (mémoire de ses scripts + cross-pôle déclaré dans ``pole.yaml``) puis
« agit » en résumant ce qu'il a lu. Sous D-017, un vrai agent appellerait ici le
cerveau (``claude -p``) avec fallback heuristique ; la démo se contente d'une
heuristique pure pour rester testable hors-ligne.
"""

from __future__ import annotations

from argos_ops.poles.agent import AgentContext, AgentResult, BaseAgent


class ExampleAgent(BaseAgent):
    """Lit la mémoire visible et résume le fait le plus récent (heuristique)."""

    pole = "_example"
    name = "ExampleAgent"

    async def act(self, context: AgentContext) -> AgentResult:
        records = context.all_records()
        if not records:
            return AgentResult(
                status="skipped",
                summary="Aucun fait en mémoire — rien à faire.",
            )
        latest = records[0]
        action = (
            f"Lu {len(records)} fait(s) ; le plus récent est un '{latest.kind}' "
            f"du script '{latest.script}' (pôle '{latest.pole}')."
        )
        return AgentResult(status="success", summary=action, actions=[action])
