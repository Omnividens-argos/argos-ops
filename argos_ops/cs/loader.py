"""Chargement YAML des customers + tickets pour les bots CS (P22.G).

Source unique pour HealthScoreBot, UpsellSpotter, ChurnPredictor,
OnboardingBot, NPSCollector, ReviewBot, KBUpdater, EscalationRouter —
toute évolution de schéma se fait ici.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

import yaml

from argos_ops.cs.models import (
    Customer,
    CustomerPlan,
    CustomerUsage,
    SupportTicket,
    TicketPriority,
)


def _as_date(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


def load_customers(path: Path) -> list[Customer]:
    """Charge la liste customers depuis ``data/cs/customers.yaml``.

    Schéma YAML attendu ::

        customers:
          - customer_id: "acme-sa"
            name: "Acme SA"
            contact_email: "marc@acme.fr"
            contact_name: "Marc Dupont"
            plan: "pro"
            signup_date: "2026-04-01"
            onboarding_done_at: "2026-04-15"  # optionnel
            last_renew_at: "2026-04-01"        # optionnel
            last_nps_at: "2026-04-30"          # optionnel
            last_nps: 9                         # 0-10 optionnel
            last_review_at: null                # optionnel
            tickets_30d: 1                      # défaut 0
            usage:
              scans_this_month: 142
              scans_quota: 200
              last_login_days_ago: 3
    """
    if not path.exists():
        return []
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    entries = raw.get("customers", [])
    out: list[Customer] = []
    for entry in entries:
        usage_raw = entry.get("usage", {}) or {}
        usage = CustomerUsage(
            scans_this_month=int(usage_raw.get("scans_this_month", 0)),
            scans_quota=int(usage_raw.get("scans_quota", 0)),
            last_login_days_ago=(
                int(usage_raw["last_login_days_ago"])
                if usage_raw.get("last_login_days_ago") is not None
                else None
            ),
        )
        out.append(
            Customer(
                customer_id=entry["customer_id"],
                name=entry["name"],
                contact_email=entry["contact_email"],
                contact_name=entry.get("contact_name", ""),
                plan=CustomerPlan(entry["plan"]),
                signup_date=_as_date(entry["signup_date"]) or date.today(),
                onboarding_done_at=_as_date(entry.get("onboarding_done_at")),
                last_renew_at=_as_date(entry.get("last_renew_at")),
                last_nps_at=_as_date(entry.get("last_nps_at")),
                last_nps=(int(entry["last_nps"]) if entry.get("last_nps") is not None else None),
                last_review_at=_as_date(entry.get("last_review_at")),
                usage=usage,
                tickets_30d=int(entry.get("tickets_30d", 0)),
            )
        )
    return out


def load_tickets(path: Path) -> list[SupportTicket]:
    """Charge les tickets support depuis ``data/support/tickets.yaml``.

    Schéma YAML attendu ::

        tickets:
          - ticket_id: "TCK-2026-0042"
            customer_id: "acme-sa"
            subject: "Scan bloque sur /api"
            body: "Le scan ne finit jamais quand on cible l'API GraphQL..."
            opened_at: "2026-05-20"
            plan: "pro"
            priority: "P1"           # optionnel — sinon classifié
            status: "open"           # open | in_progress | resolved
            last_response_at: null
    """
    if not path.exists():
        return []
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    entries = raw.get("tickets", [])
    out: list[SupportTicket] = []
    for entry in entries:
        priority_raw = entry.get("priority")
        out.append(
            SupportTicket(
                ticket_id=entry["ticket_id"],
                customer_id=entry["customer_id"],
                subject=entry["subject"],
                body=entry.get("body", ""),
                opened_at=_as_date(entry["opened_at"]) or date.today(),
                priority=TicketPriority(priority_raw) if priority_raw else None,
                plan=CustomerPlan(entry.get("plan", "starter")),
                status=entry.get("status", "open"),
                last_response_at=_as_date(entry.get("last_response_at")),
            )
        )
    return out


__all__ = ["load_customers", "load_tickets"]
