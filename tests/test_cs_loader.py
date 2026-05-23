"""Tests unitaires de ``argos_ops.cs.loader`` (P22.G)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import yaml

from argos_ops.cs.loader import load_customers, load_tickets
from argos_ops.cs.models import CustomerPlan, TicketPriority


def test_load_customers_empty_file_returns_empty_list(tmp_path: Path) -> None:
    path = tmp_path / "customers.yaml"
    path.write_text("customers: []\n", encoding="utf-8")
    assert load_customers(path) == []


def test_load_customers_missing_file_returns_empty_list(tmp_path: Path) -> None:
    assert load_customers(tmp_path / "missing.yaml") == []


def test_load_customers_parses_full_entry(tmp_path: Path) -> None:
    path = tmp_path / "customers.yaml"
    payload = {
        "customers": [
            {
                "customer_id": "acme-sa",
                "name": "Acme SA",
                "contact_email": "marc@acme.fr",
                "contact_name": "Marc Dupont",
                "plan": "pro",
                "signup_date": "2026-04-01",
                "onboarding_done_at": "2026-04-15",
                "last_nps_at": "2026-04-30",
                "last_nps": 9,
                "tickets_30d": 2,
                "usage": {
                    "scans_this_month": 142,
                    "scans_quota": 200,
                    "last_login_days_ago": 3,
                },
            }
        ]
    }
    path.write_text(yaml.safe_dump(payload, allow_unicode=True), encoding="utf-8")
    customers = load_customers(path)
    assert len(customers) == 1
    c = customers[0]
    assert c.plan == CustomerPlan.PRO
    assert c.signup_date == date(2026, 4, 1)
    assert c.usage.scans_this_month == 142
    assert c.last_nps == 9


def test_load_tickets_parses_priority_or_none(tmp_path: Path) -> None:
    path = tmp_path / "tickets.yaml"
    payload = {
        "tickets": [
            {
                "ticket_id": "TCK-1",
                "customer_id": "acme-sa",
                "subject": "Bug scan",
                "body": "...",
                "opened_at": "2026-05-20",
                "plan": "pro",
                "priority": "P1",
            },
            {
                "ticket_id": "TCK-2",
                "customer_id": "acme-sa",
                "subject": "Question",
                "body": "...",
                "opened_at": "2026-05-21",
                "plan": "starter",
            },
        ]
    }
    path.write_text(yaml.safe_dump(payload, allow_unicode=True), encoding="utf-8")
    tickets = load_tickets(path)
    assert len(tickets) == 2
    assert tickets[0].priority == TicketPriority.P1
    assert tickets[1].priority is None
