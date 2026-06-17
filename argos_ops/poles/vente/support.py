"""Support / triage du pôle Vente (archi v2, S4) — P0/P1/P2 + SLA.

Charge ``data/poles/vente/support/tickets.yaml`` via
:func:`argos_ops.cs.loader.load_tickets` et réutilise le scoring pur de
:mod:`argos_ops.cs.scoring` (:func:`classify_ticket_priority`,
:func:`sla_response_hours`, :func:`sla_breached`) pour produire un
:class:`~argos_ops.cs.models.TriagedTicket` par ticket.

« Le LLM propose, Python tranche » : l'override humain (``ticket.priority``) est
prioritaire et la classification heuristique ne se fait jamais déclasser. Le
``VenteAgent`` lit ensuite la mémoire écrite par le script ``escalation_router``.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from argos_ops.cs.loader import load_tickets
from argos_ops.cs.models import SupportTicket, TicketPriority, TriagedTicket
from argos_ops.cs.scoring import classify_ticket_priority, sla_breached, sla_response_hours
from argos_ops.poles.config import POLES_DIR

VENTE_POLE = "vente"

_PRIORITY_RANK: dict[TicketPriority, int] = {
    TicketPriority.P0: 0,
    TicketPriority.P1: 1,
    TicketPriority.P2: 2,
}


def tickets_path(*, poles_root: Path = POLES_DIR) -> Path:
    return poles_root / VENTE_POLE / "support" / "tickets.yaml"


def load_support_tickets(*, poles_root: Path = POLES_DIR) -> list[SupportTicket]:
    """Charge les tickets support. Absent ⇒ ``[]`` (best-effort)."""
    return load_tickets(tickets_path(poles_root=poles_root))


def triage(tickets: list[SupportTicket], *, today: date | None = None) -> list[TriagedTicket]:
    """Classifie + calcule le SLA de chaque ticket ouvert.

    Trié par priorité (P0 d'abord) puis breach d'abord. Les tickets ``resolved``
    sont écartés (plus dans la file active).
    """
    today = today or date.today()
    triaged: list[TriagedTicket] = []
    for ticket in tickets:
        if ticket.status == "resolved":
            continue
        priority = classify_ticket_priority(ticket)
        breached = sla_breached(ticket, priority, today=today)
        reason = "override humain" if ticket.priority is not None else "classification mots-clés"
        triaged.append(
            TriagedTicket(
                ticket=ticket,
                priority=priority,
                sla_response_hours=sla_response_hours(priority, ticket.plan),
                sla_breached=breached,
                reason=reason,
            )
        )
    triaged.sort(key=lambda t: (_PRIORITY_RANK[t.priority], not t.sla_breached))
    return triaged


__all__ = ["load_support_tickets", "tickets_path", "triage"]
