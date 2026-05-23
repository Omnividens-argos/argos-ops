"""Tests unitaires de ``argos_ops.agents.escalation_router`` (P22.G)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import yaml

from argos_ops.agents.escalation_router import (
    _persist_triage,
    build_escalation_embed,
    triage_tickets,
)
from argos_ops.cs.models import CustomerPlan, SupportTicket, TicketPriority


def _ticket(**overrides: object) -> SupportTicket:
    base: dict[str, object] = dict(
        ticket_id="TCK-1",
        customer_id="acme-sa",
        subject="Question simple",
        body="...",
        opened_at=date(2026, 5, 22),
        plan=CustomerPlan.PRO,
        status="open",
    )
    base.update(overrides)
    return SupportTicket(**base)  # type: ignore[arg-type]


def test_triage_classifies_p0_p1_p2() -> None:
    tickets = [
        _ticket(ticket_id="t1", subject="urgent prod down"),
        _ticket(ticket_id="t2", subject="Bug régression scan"),
        _ticket(ticket_id="t3", subject="Question sur export"),
    ]
    report = triage_tickets(tickets, today=date(2026, 5, 23))
    assert report.p0_open == 1
    assert report.p1_open == 1
    assert report.p2_open == 1


def test_triage_ignores_resolved() -> None:
    tickets = [_ticket(ticket_id="t1", status="resolved")]
    report = triage_tickets(tickets, today=date(2026, 5, 23))
    assert report.p0_open == report.p1_open == report.p2_open == 0


def test_triage_flags_sla_breach() -> None:
    tickets = [
        _ticket(
            ticket_id="t1",
            subject="urgent prod down",
            opened_at=date(2026, 5, 20),
        )
    ]
    report = triage_tickets(tickets, today=date(2026, 5, 23))
    assert len(report.breached) == 1
    assert report.breached[0].priority == TicketPriority.P0


def test_persist_triage_writes_yaml(tmp_path: Path) -> None:
    tickets = [_ticket(ticket_id="t1", subject="urgent prod down")]
    report = triage_tickets(tickets, today=date(2026, 5, 23))
    path = tmp_path / "triage_2026-05-23.yaml"
    _persist_triage(path, report, day=date(2026, 5, 23))
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert raw["triage_date"] == "2026-05-23"
    assert raw["p0_open"] == 1
    assert raw["tickets"][0]["priority"] == "P0"


def test_embed_red_when_breach() -> None:
    tickets = [
        _ticket(
            ticket_id="t1",
            subject="urgent prod down",
            opened_at=date(2026, 5, 20),
        )
    ]
    report = triage_tickets(tickets, today=date(2026, 5, 23))
    assert build_escalation_embed(report).color == 0xE74C3C


def test_embed_yellow_when_p0_p1_open_no_breach() -> None:
    tickets = [_ticket(ticket_id="t1", subject="bug crash")]
    report = triage_tickets(tickets, today=date(2026, 5, 22))
    # P1 starter = 4h, ouvert le 22, on est le 22 → pas breach
    assert build_escalation_embed(report).color == 0xF1C40F


def test_embed_green_when_only_p2() -> None:
    tickets = [_ticket(ticket_id="t1", subject="Question simple")]
    report = triage_tickets(tickets, today=date(2026, 5, 22))
    assert build_escalation_embed(report).color == 0x2ECC71
