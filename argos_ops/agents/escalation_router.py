"""EscalationRouter — Support Lead (P22.G CS Sprint 7).

Lit ``data/support/tickets.yaml``, classifie chaque ticket open en
P0/P1/P2 (sujet+body keywords sauf override manuel), calcule le SLA
réponse selon priorité x plan, et flag les SLA breach.

Écrit ``data/support/triage_<YYYY-MM-DD>.yaml`` + Discord rouge si ≥1
SLA breach, jaune si ≥1 P0/P1 ouvert sans breach. Read-only sur le YAML
source — le founder garde la main sur les tickets.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

import yaml
from loguru import logger

from argos_ops.agents.base import BaseAgent, IOItem, RunResult
from argos_ops.config import REPO_ROOT, get_settings
from argos_ops.cs.loader import load_tickets
from argos_ops.cs.models import SupportTicket, TicketPriority, TriagedTicket
from argos_ops.cs.scoring import (
    classify_ticket_priority,
    sla_breached,
    sla_response_hours,
)
from argos_ops.notifications.discord import (
    GREEN,
    RED,
    YELLOW,
    Embed,
    EmbedField,
    send_embed,
)

DEFAULT_TICKETS_PATH: Path = REPO_ROOT / "data" / "support" / "tickets.yaml"
DEFAULT_TRIAGE_DIR: Path = REPO_ROOT / "data" / "support"


@dataclass
class EscalationReport:
    triaged: list[TriagedTicket] = field(default_factory=list)
    breached: list[TriagedTicket] = field(default_factory=list)
    p0_open: int = 0
    p1_open: int = 0
    p2_open: int = 0

    def summary(self) -> str:
        return (
            f"triaged={len(self.triaged)} p0={self.p0_open} p1={self.p1_open} "
            f"p2={self.p2_open} breached={len(self.breached)}"
        )


def triage_tickets(tickets: list[SupportTicket], *, today: date) -> EscalationReport:
    """Classifie chaque ticket open et flag les SLA breach."""
    report = EscalationReport()
    for ticket in tickets:
        if ticket.status == "resolved":
            continue
        priority = classify_ticket_priority(ticket)
        sla_h = sla_response_hours(priority, ticket.plan)
        breached = sla_breached(ticket, priority, today=today)
        triaged = TriagedTicket(
            ticket=ticket,
            priority=priority,
            sla_response_hours=sla_h,
            sla_breached=breached,
            reason=(
                f"P{priority.value[-1]} {ticket.plan.value} : SLA {sla_h}h depuis "
                f"{ticket.opened_at.isoformat()}"
            ),
        )
        report.triaged.append(triaged)
        if breached:
            report.breached.append(triaged)
        if priority == TicketPriority.P0:
            report.p0_open += 1
        elif priority == TicketPriority.P1:
            report.p1_open += 1
        else:
            report.p2_open += 1
    report.breached.sort(key=lambda t: (t.priority.value, t.ticket.opened_at))
    return report


def _persist_triage(triage_path: Path, report: EscalationReport, *, day: date) -> None:
    triage_path.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = {
        "triage_date": day.isoformat(),
        "p0_open": report.p0_open,
        "p1_open": report.p1_open,
        "p2_open": report.p2_open,
        "breached_count": len(report.breached),
        "tickets": [
            {
                "ticket_id": t.ticket.ticket_id,
                "customer_id": t.ticket.customer_id,
                "subject": t.ticket.subject,
                "priority": t.priority.value,
                "sla_response_hours": t.sla_response_hours,
                "sla_breached": t.sla_breached,
                "reason": t.reason,
            }
            for t in report.triaged
        ],
    }
    triage_path.write_text(
        yaml.safe_dump(payload, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )


def build_escalation_embed(report: EscalationReport) -> Embed:
    if report.breached:
        color = RED
    elif report.p0_open > 0 or report.p1_open > 0:
        color = YELLOW
    else:
        color = GREEN
    fields = [
        EmbedField(name="P0 ouverts", value=str(report.p0_open), inline=True),
        EmbedField(name="P1 ouverts", value=str(report.p1_open), inline=True),
        EmbedField(name="P2 ouverts", value=str(report.p2_open), inline=True),
        EmbedField(name="SLA breach", value=str(len(report.breached)), inline=True),
    ]
    if report.breached:
        lines = [
            f"• [{t.priority.value}] **{t.ticket.ticket_id}** ({t.ticket.customer_id}) — "
            f"{t.ticket.subject[:60]}"
            for t in report.breached[:5]
        ]
        fields.append(EmbedField(name="Tickets breachés", value="\n".join(lines), inline=False))
    return Embed(
        title=f"EscalationRouter — {len(report.breached)} SLA breach / {report.p0_open + report.p1_open} P0-P1",
        description=(
            "Traiter en priorité — détail dans `data/support/triage_<date>.yaml`."
            if report.breached
            else "Aucun SLA dépassé."
        ),
        color=color,
        fields=fields,
        footer="Argos Ops • EscalationRouter",
    )


class EscalationRouter(BaseAgent):
    """Trie les tickets support P0/P1/P2 + flag les SLA breach."""

    name = "EscalationRouter"
    command = "/run-ticket-triage"
    breaker_name = "EscalationRouter"
    ai_act_risk_class = "minimal"

    def __init__(
        self,
        *,
        tickets_path: Path = DEFAULT_TICKETS_PATH,
        triage_dir: Path = DEFAULT_TRIAGE_DIR,
    ) -> None:
        self._tickets_path = tickets_path
        self._triage_dir = triage_dir

    async def run(self) -> RunResult:
        settings = get_settings()
        tickets = load_tickets(self._tickets_path)
        if not tickets:
            logger.info(f"EscalationRouter — aucun ticket ({self._tickets_path})")
            return RunResult(status="success", output_summary="silence (no tickets)")

        today = date.today()
        report = triage_tickets(tickets, today=today)
        triage_path = self._triage_dir / f"triage_{today.isoformat()}.yaml"
        _persist_triage(triage_path, report, day=today)

        webhook = settings.discord_webhook_ops_logs or settings.discord_webhook_alerts
        if webhook is not None and (report.breached or report.p0_open > 0):
            try:
                await send_embed(webhook, build_escalation_embed(report))
            except Exception as exc:
                logger.warning(f"EscalationRouter — notif Discord échouée : {exc}")

        inputs = [
            IOItem(
                label="Tickets support",
                kind="file",
                detail=(
                    f"P0={report.p0_open} P1={report.p1_open} "
                    f"P2={report.p2_open} · {len(report.breached)} SLA breach"
                ),
                ref="data/support/tickets.yaml",
                count=len(tickets),
            )
        ]
        outputs: list[IOItem] = [
            IOItem(
                label="Triage tickets (priorité + SLA)",
                kind="file",
                detail=f"{len(report.breached)} SLA breach flaggé(s)",
                ref=f"data/support/{triage_path.name}",
                count=len(report.triaged),
            )
        ]
        if report.breached:
            outputs.append(
                IOItem(
                    label="Alerte Discord SLA breach",
                    kind="discord",
                    count=len(report.breached),
                )
            )

        return RunResult(
            status="success",
            output_summary=report.summary(),
            inputs=inputs,
            outputs=outputs,
        )


__all__ = [
    "DEFAULT_TICKETS_PATH",
    "DEFAULT_TRIAGE_DIR",
    "EscalationReport",
    "EscalationRouter",
    "build_escalation_embed",
    "triage_tickets",
]
