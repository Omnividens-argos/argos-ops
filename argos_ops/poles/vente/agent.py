"""``VenteAgent`` — le cerveau du pôle Vente & Relation Client (archi v2, S4).

Le pôle Vente est **en aval** de la Veille (signaux d'achat : ``intent_signal`` /
``breach`` / ``cve`` / ``regulatory``) et du Marketing (message / angle). Son agent
lit sa propre mémoire (faits écrits par ses 12 scripts : tickets, santé, churn,
inbox triée, leads qualifiés, RDV, upsell…) **plus** la mémoire de ces deux pôles
en cross-pôle (``reads_cross_pole: [veille, marketing]`` dans ``pole.yaml``), puis
**synthétise un plan d'actions priorisé**
(:func:`~argos_ops.poles.vente.plan.plan_actions`).

**Garde-fou central** : avant de planifier, l'agent lit l'état de conformité
Bloctel (:func:`~argos_ops.poles.vente.outreach.outbound_frozen`, donnée
déterministe de son propre pôle) et **gèle** toute action d'outbound s'il est
armé. « Le LLM propose, Python tranche » : sous D-017 le cerveau réel (``claude
-p``) surchargerait :meth:`_plan` pour affiner les angles de relance, mais ne peut
jamais lever ce gel. Le fallback heuristique reste :func:`plan_actions`. C'est le
strict miroir du breaker ``ad_spend_runaway`` du pôle Pub.
"""

from __future__ import annotations

from argos_ops.poles.agent import AgentContext, AgentResult, BaseAgent
from argos_ops.poles.memory import MemoryRecord
from argos_ops.poles.vente import outreach
from argos_ops.poles.vente.plan import VentePlan, plan_actions


class VenteAgent(BaseAgent):
    """Synthétise Veille/Marketing + mémoire propre en plan d'actions borné par Bloctel."""

    pole = "vente"
    name = "VenteAgent"

    def _plan(self, records: list[MemoryRecord], *, outbound_frozen: bool) -> list[VentePlan]:
        """Point d'extension du cerveau (D-017). Défaut = heuristique pure."""
        return plan_actions(records, outbound_frozen=outbound_frozen)

    async def act(self, context: AgentContext) -> AgentResult:
        # Garde-fou Python : l'état Bloctel borne le plan AVANT toute décision.
        outbound_frozen = outreach.outbound_frozen(poles_root=self.poles_root)
        records = context.all_records()
        if not records:
            return AgentResult(
                status="skipped",
                summary="Aucune mémoire (propre ni cross-pôle) — rien à planifier.",
            )

        plans = self._plan(records, outbound_frozen=outbound_frozen)
        if not plans:
            return AgentResult(
                status="skipped",
                summary=(
                    f"{len(records)} fait(s) visible(s) mais aucune action commerciale "
                    "à planifier (ni ticket, ni compte à risque, ni lead, ni RDV)."
                ),
            )

        actions = [
            f"[{p.severity}] {p.action} ({p.kind})"
            f"{' [GELÉ Bloctel]' if p.suppressed_by_compliance else ''}"
            for p in plans
        ]
        suppressed = sum(1 for p in plans if p.suppressed_by_compliance)
        critical = sum(1 for p in plans if p.severity == "critical")
        seen = [p for p in ("veille", "marketing") if p in context.cross_pole]
        cross_note = f" (cross-pôle : {', '.join(seen)})" if seen else ""
        compliance_note = (
            f" — outbound GELÉ (Bloctel), {suppressed} action(s) suspendue(s)"
            if outbound_frozen and suppressed
            else ""
        )
        summary = (
            f"{len(plans)} action(s) planifiée(s) depuis {len(records)} fait(s)"
            f"{cross_note} — {critical} critique(s){compliance_note}"
        )
        return AgentResult(status="success", summary=summary, actions=actions)


__all__ = ["VenteAgent"]
