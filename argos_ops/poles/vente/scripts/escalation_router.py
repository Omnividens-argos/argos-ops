"""``EscalationRouterScript`` — triage support P0/P1/P2 + SLA (Vente, archi v2, S4).

Bras déterministe : charge ``data/poles/vente/support/tickets.yaml``, classe chaque
ticket ouvert (:func:`argos_ops.poles.vente.support.triage`) et écrit un fait
``kind="ticket"`` — **important** si P0 ou SLA dépassé. Le ``VenteAgent`` priorise
ensuite ces tickets. « Le LLM propose, Python tranche » : un override humain
prioritaire et la classification mots-clés ne se fait jamais déclasser.
"""

from __future__ import annotations

from pathlib import Path

from argos_ops.cs.models import TicketPriority
from argos_ops.poles.base import BaseScript, ScriptResult
from argos_ops.poles.config import POLES_DIR
from argos_ops.poles.vente import support


class EscalationRouterScript(BaseScript):
    """Classifie les tickets ouverts et les mémorise (``kind="ticket"``)."""

    pole = "vente"
    name = "escalation_router"

    def __init__(self, *, poles_root: Path = POLES_DIR) -> None:
        super().__init__(poles_root=poles_root)

    async def run(self) -> ScriptResult:
        tickets = support.load_support_tickets(poles_root=self.poles_root)
        triaged = support.triage(tickets)
        if not triaged:
            return ScriptResult(
                status="success",
                summary="Aucun ticket ouvert (data/poles/vente/support/tickets.yaml).",
                written=[],
            )

        written = []
        breached = 0
        p0 = 0
        for t in triaged:
            tags: tuple[str, ...] = (t.priority.value,)
            if t.sla_breached:
                tags = (*tags, "breach", "critical")
                breached += 1
            elif t.priority == TicketPriority.P0:
                tags = (*tags, "critical")
            if t.priority == TicketPriority.P0:
                p0 += 1
            important = t.priority == TicketPriority.P0 or t.sla_breached
            record = await self.write_memory(
                f"[{t.priority.value}] {t.ticket.subject} ({t.ticket.customer_id}) — "
                f"SLA {t.sla_response_hours}h{' DÉPASSÉ' if t.sla_breached else ''}",
                kind="ticket",
                tags=tags,
                important=important,
                source=t.ticket.customer_id,
            )
            written.append(record)

        return ScriptResult(
            status="success",
            summary=f"{len(triaged)} ticket(s) ouvert(s) — {p0} P0, {breached} SLA dépassé(s)",
            written=written,
        )


__all__ = ["EscalationRouterScript"]
