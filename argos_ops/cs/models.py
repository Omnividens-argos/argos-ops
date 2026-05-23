"""Dataclasses CS partagées par les 8 bots Sprint 7 (P22.G).

Conteneurs immuables uniquement. Sérialisation YAML faite par
``argos_ops.cs.loader``. Templating email par ``argos_ops.cs.templates``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum


class CustomerPlan(StrEnum):
    """Plans tarifaires Argos (cohérent avec Stripe products)."""

    STARTER = "starter"
    PRO = "pro"
    ENTERPRISE = "enterprise"


@dataclass(frozen=True)
class CustomerUsage:
    """Mesures d'usage produit injectées à la main par le fondateur."""

    scans_this_month: int = 0
    scans_quota: int = 0  # 0 = plan sans quota (enterprise sur mesure)
    last_login_days_ago: int | None = None  # None = jamais loggé


@dataclass(frozen=True)
class Customer:
    """Snapshot client — input commun de tous les bots CS.

    Le YAML source est saisi à la main par le fondateur ; le bot ne le
    réécrit pas (sauf NPSCollector qui patch ``last_nps_at`` après
    drafting).
    """

    customer_id: str  # slug stable, ex : "acme-sa"
    name: str
    contact_email: str
    contact_name: str
    plan: CustomerPlan
    signup_date: date
    onboarding_done_at: date | None = None
    last_renew_at: date | None = None
    last_nps_at: date | None = None
    last_nps: int | None = None  # score 0-10
    last_review_at: date | None = None
    usage: CustomerUsage = field(default_factory=CustomerUsage)
    tickets_30d: int = 0  # nombre de tickets ouverts dans les 30 derniers jours


class HealthBand(StrEnum):
    """Bande santé du compte — pilote la couleur Discord et les alertes."""

    GREEN = "green"
    YELLOW = "yellow"
    RED = "red"


@dataclass(frozen=True)
class HealthScore:
    """Output HealthScoreBot pour un compte."""

    customer_id: str
    score: int  # 0-100
    band: HealthBand
    drivers: list[str]  # ex : ["usage 71% quota", "1 ticket 30j", "NPS 9"]


class TicketPriority(StrEnum):
    """Priorité support — calculée à partir du sujet + plan."""

    P0 = "P0"  # incident bloquant prod
    P1 = "P1"  # bug majeur sans contournement
    P2 = "P2"  # question / amélioration


@dataclass(frozen=True)
class SupportTicket:
    """Ticket support entré à la main ou ingéré depuis l'EmailBot.

    Les SLA Argos (cf. ``docs/ESCALATION_RULES.md``) :
    - P0 : 1h response, 4h resolution
    - P1 : 4h response, 24h resolution
    - P2 : 24h response, 5j resolution
    """

    ticket_id: str
    customer_id: str
    subject: str
    body: str
    opened_at: date
    priority: TicketPriority | None = None  # None = à classifier
    plan: CustomerPlan = CustomerPlan.STARTER
    status: str = "open"  # open | in_progress | resolved
    last_response_at: date | None = None


@dataclass(frozen=True)
class TriagedTicket:
    """Output EscalationRouter."""

    ticket: SupportTicket
    priority: TicketPriority
    sla_response_hours: int
    sla_breached: bool
    reason: str


@dataclass(frozen=True)
class ChurnSignal:
    """Output ChurnPredictor pour un compte à risque."""

    customer_id: str
    risk_score: int  # 0-100
    signals: list[str]


@dataclass(frozen=True)
class UpsellCandidate:
    """Output UpsellSpotter pour un compte mûr pour upsell."""

    customer_id: str
    usage_ratio: float  # ex : 0.85 = 85% du quota plan
    suggested_plan: CustomerPlan
    reason: str


__all__ = [
    "ChurnSignal",
    "Customer",
    "CustomerPlan",
    "CustomerUsage",
    "HealthBand",
    "HealthScore",
    "SupportTicket",
    "TicketPriority",
    "TriagedTicket",
    "UpsellCandidate",
]
