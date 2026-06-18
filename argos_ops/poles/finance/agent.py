"""``FinanceAgent`` — le cerveau du pôle Finance & Conformité (archi v2, S5).

Le pôle Finance est **en aval** de la Vente (un devis envoyé → une facture à
émettre + un nouveau traitement RGPD à enregistrer). Son agent lit sa propre
mémoire (faits écrits par ses 11 scripts : MRR, dunning, treasury, fiscal, RGPD,
AI Act, contrats, dépenses, rapprochement, incidents) **plus** la mémoire de la
Vente en cross-pôle (``reads_cross_pole: [vente]``), puis **synthétise un plan
d'actions priorisé** (:func:`~argos_ops.poles.finance.plan.plan_actions`).

**Garde-fou central** : avant de planifier, l'agent lit l'état de conformité
(:func:`~argos_ops.poles.finance.compliance.compliance_blocking`, donnée
déterministe de son propre pôle) et **gèle** tout onboarding d'un nouveau
traitement (facturer un nouveau client) s'il est armé. « Le LLM propose, Python
tranche » : sous D-017 le cerveau réel (``claude -p``) surchargerait :meth:`_plan`
pour affiner les priorités, mais ne peut jamais lever ce gel. Le fallback
heuristique reste :func:`plan_actions`. C'est le strict miroir du gel Bloctel du
pôle Vente / du breaker ``ad_spend_runaway`` du pôle Pub.
"""

from __future__ import annotations

from argos_ops.poles.agent import AgentContext, AgentResult, BaseAgent
from argos_ops.poles.finance import compliance
from argos_ops.poles.finance.plan import FinancePlan, plan_actions
from argos_ops.poles.memory import MemoryRecord


class FinanceAgent(BaseAgent):
    """Synthétise mémoire Finance + Vente en plan d'actions borné par la conformité."""

    pole = "finance"
    name = "FinanceAgent"

    def _plan(self, records: list[MemoryRecord], *, compliance_blocking: bool) -> list[FinancePlan]:
        """Point d'extension du cerveau (D-017). Défaut = heuristique pure."""
        return plan_actions(records, compliance_blocking=compliance_blocking)

    async def act(self, context: AgentContext) -> AgentResult:
        # Garde-fou Python : l'état conformité borne le plan AVANT toute décision.
        blocking = compliance.compliance_blocking(poles_root=self.poles_root)
        records = context.all_records()
        if not records:
            return AgentResult(
                status="skipped",
                summary="Aucune mémoire (propre ni cross-pôle) — rien à planifier.",
            )

        plans = self._plan(records, compliance_blocking=blocking)
        if not plans:
            return AgentResult(
                status="skipped",
                summary=(
                    f"{len(records)} fait(s) visible(s) mais aucune action finance/conformité "
                    "à planifier (ni relance, ni échéance, ni gap, ni facture à émettre)."
                ),
            )

        actions = [
            f"[{p.severity}] {p.action} ({p.kind})"
            f"{' [GELÉ conformité]' if p.suppressed_by_compliance else ''}"
            for p in plans
        ]
        suppressed = sum(1 for p in plans if p.suppressed_by_compliance)
        critical = sum(1 for p in plans if p.severity == "critical")
        cross_note = " (cross-pôle : vente)" if "vente" in context.cross_pole else ""
        compliance_note = (
            f" — onboarding GELÉ (conformité), {suppressed} action(s) suspendue(s)"
            if blocking and suppressed
            else ""
        )
        summary = (
            f"{len(plans)} action(s) planifiée(s) depuis {len(records)} fait(s)"
            f"{cross_note} — {critical} critique(s){compliance_note}"
        )
        return AgentResult(status="success", summary=summary, actions=actions)


__all__ = ["FinanceAgent"]
