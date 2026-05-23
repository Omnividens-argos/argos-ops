"""Tests unitaires de ``argos_ops.cs.scoring`` (P22.G)."""

from __future__ import annotations

from datetime import date

from argos_ops.cs.models import (
    Customer,
    CustomerPlan,
    CustomerUsage,
    HealthBand,
    SupportTicket,
    TicketPriority,
)
from argos_ops.cs.scoring import (
    classify_ticket_priority,
    compute_health_score,
    detect_churn_signals,
    detect_upsell_candidate,
    sla_breached,
    sla_response_hours,
)


def _customer(**overrides: object) -> Customer:
    base: dict[str, object] = dict(
        customer_id="acme-sa",
        name="Acme SA",
        contact_email="marc@acme.fr",
        contact_name="Marc Dupont",
        plan=CustomerPlan.PRO,
        signup_date=date(2026, 4, 1),
        usage=CustomerUsage(scans_this_month=120, scans_quota=200, last_login_days_ago=2),
        tickets_30d=1,
        last_nps=8,
    )
    base.update(overrides)
    return Customer(**base)  # type: ignore[arg-type]


def test_health_score_green_for_healthy_account() -> None:
    score = compute_health_score(_customer())
    assert score.band == HealthBand.GREEN
    assert score.score >= 70


def test_health_score_red_for_inactive_detractor() -> None:
    customer = _customer(
        usage=CustomerUsage(scans_this_month=2, scans_quota=200, last_login_days_ago=40),
        tickets_30d=8,
        last_nps=3,
    )
    score = compute_health_score(customer)
    assert score.band == HealthBand.RED
    assert score.score < 40
    assert any("détracteur" in d for d in score.drivers)


def test_detect_upsell_candidate_when_saturated() -> None:
    customer = _customer(
        usage=CustomerUsage(scans_this_month=180, scans_quota=200, last_login_days_ago=1)
    )
    candidate = detect_upsell_candidate(customer)
    assert candidate is not None
    assert candidate.usage_ratio == 0.9
    assert candidate.suggested_plan == CustomerPlan.ENTERPRISE


def test_no_upsell_when_under_threshold() -> None:
    customer = _customer(
        usage=CustomerUsage(scans_this_month=50, scans_quota=200, last_login_days_ago=1)
    )
    assert detect_upsell_candidate(customer) is None


def test_detect_churn_signals_returns_none_for_healthy() -> None:
    assert detect_churn_signals(_customer()) is None


def test_detect_churn_signals_flags_detractor_inactive() -> None:
    customer = _customer(
        usage=CustomerUsage(scans_this_month=1, scans_quota=200, last_login_days_ago=45),
        last_nps=2,
        tickets_30d=7,
    )
    signal = detect_churn_signals(customer)
    assert signal is not None
    assert signal.risk_score >= 70


def test_classify_ticket_priority_p0_keyword() -> None:
    ticket = SupportTicket(
        ticket_id="t1",
        customer_id="acme-sa",
        subject="URGENT: prod down sur scans planifiés",
        body="Toute la prod est tombée ce matin, aucun scan ne démarre.",
        opened_at=date(2026, 5, 23),
        plan=CustomerPlan.PRO,
    )
    assert classify_ticket_priority(ticket) == TicketPriority.P0


def test_classify_ticket_priority_p1_keyword() -> None:
    ticket = SupportTicket(
        ticket_id="t2",
        customer_id="acme-sa",
        subject="Le scan reste bloqué",
        body="Le scan ne finit pas sur notre API GraphQL — bug?",
        opened_at=date(2026, 5, 23),
        plan=CustomerPlan.PRO,
    )
    assert classify_ticket_priority(ticket) == TicketPriority.P1


def test_classify_ticket_priority_p2_default() -> None:
    ticket = SupportTicket(
        ticket_id="t3",
        customer_id="acme-sa",
        subject="Question sur l'export PDF",
        body="Comment exporter en PDF ?",
        opened_at=date(2026, 5, 23),
        plan=CustomerPlan.STARTER,
    )
    assert classify_ticket_priority(ticket) == TicketPriority.P2


def test_sla_response_hours_enterprise_halved() -> None:
    assert sla_response_hours(TicketPriority.P0, CustomerPlan.PRO) == 1
    assert sla_response_hours(TicketPriority.P1, CustomerPlan.PRO) == 4
    assert sla_response_hours(TicketPriority.P1, CustomerPlan.ENTERPRISE) == 2
    assert sla_response_hours(TicketPriority.P2, CustomerPlan.ENTERPRISE) == 24


def test_sla_breached_when_no_response_after_deadline() -> None:
    ticket = SupportTicket(
        ticket_id="t4",
        customer_id="acme-sa",
        subject="...",
        body="...",
        opened_at=date(2026, 5, 18),
        plan=CustomerPlan.STARTER,
        priority=TicketPriority.P1,
    )
    today = date(2026, 5, 23)
    # P1 starter = 4h SLA → 1j cutoff, dépassé depuis 5j
    assert sla_breached(ticket, TicketPriority.P1, today=today) is True


def test_sla_not_breached_once_responded() -> None:
    ticket = SupportTicket(
        ticket_id="t5",
        customer_id="acme-sa",
        subject="...",
        body="...",
        opened_at=date(2026, 5, 18),
        plan=CustomerPlan.STARTER,
        priority=TicketPriority.P2,
        last_response_at=date(2026, 5, 19),
    )
    assert sla_breached(ticket, TicketPriority.P2, today=date(2026, 5, 23)) is False
