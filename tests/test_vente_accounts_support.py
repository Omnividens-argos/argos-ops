"""Tests comptes + support du pôle Vente (archi v2, S4)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from argos_ops.poles.vente import accounts, support

_CUSTOMERS = (
    "customers:\n"
    "  - customer_id: green\n    name: Green\n    contact_email: a@green.fr\n    contact_name: A\n"
    "    plan: pro\n    signup_date: '2026-05-01'\n    last_nps: 9\n    tickets_30d: 0\n"
    "    usage: {scans_this_month: 142, scans_quota: 200, last_login_days_ago: 2}\n"
    "  - customer_id: saturated\n    name: Sat\n    contact_email: b@sat.fr\n    contact_name: B\n"
    "    plan: pro\n    signup_date: '2026-03-01'\n    last_nps: 8\n    tickets_30d: 1\n"
    "    usage: {scans_this_month: 190, scans_quota: 200, last_login_days_ago: 1}\n"
    "  - customer_id: dying\n    name: Dy\n    contact_email: c@dy.fr\n    contact_name: C\n"
    "    plan: starter\n    signup_date: '2026-02-01'\n    last_nps: 3\n    tickets_30d: 6\n"
    "    usage: {scans_this_month: 4, scans_quota: 50, last_login_days_ago: 40}\n"
)


def _write_customers(root: Path) -> None:
    d = root / "vente" / "cs"
    d.mkdir(parents=True, exist_ok=True)
    (d / "customers.yaml").write_text(_CUSTOMERS, encoding="utf-8")


def test_health_bands(tmp_path: Path) -> None:
    _write_customers(tmp_path)
    scores = accounts.score_health(accounts.load_accounts(poles_root=tmp_path))
    bands = {s.customer_id: s.band.value for s in scores}
    assert bands["dying"] == "red"
    assert bands["green"] == "green"
    # Trié du plus bas au plus haut.
    assert scores[0].customer_id == "dying"


def test_churn_urgent(tmp_path: Path) -> None:
    _write_customers(tmp_path)
    churn = accounts.detect_churn(accounts.load_accounts(poles_root=tmp_path))
    dying = next(c for c in churn if c.customer_id == "dying")
    assert dying.risk_score >= accounts.URGENT_CHURN_THRESHOLD


def test_upsell_detects_saturated(tmp_path: Path) -> None:
    _write_customers(tmp_path)
    ups = accounts.detect_upsells(accounts.load_accounts(poles_root=tmp_path))
    assert any(u.customer_id == "saturated" and u.suggested_plan.value == "enterprise" for u in ups)


def _write_tickets(root: Path, body: str) -> None:
    d = root / "vente" / "support"
    d.mkdir(parents=True, exist_ok=True)
    (d / "tickets.yaml").write_text(body, encoding="utf-8")


def test_triage_p0_breach(tmp_path: Path) -> None:
    _write_tickets(
        tmp_path,
        "tickets:\n"
        "  - ticket_id: T1\n    customer_id: c\n    subject: prod down\n    body: urgent incident\n"
        "    opened_at: '2026-06-10'\n    plan: pro\n"
        "  - ticket_id: T2\n    customer_id: c\n    subject: question\n    body: comment faire\n"
        "    opened_at: '2026-06-16'\n    plan: pro\n    last_response_at: '2026-06-16'\n"
        "  - ticket_id: T3\n    customer_id: c\n    subject: resolved one\n    body: x\n"
        "    opened_at: '2026-06-01'\n    status: resolved\n",
    )
    triaged = support.triage(
        support.load_support_tickets(poles_root=tmp_path), today=date(2026, 6, 17)
    )
    ids = [t.ticket.ticket_id for t in triaged]
    assert "T3" not in ids  # resolved écarté
    t1 = next(t for t in triaged if t.ticket.ticket_id == "T1")
    assert t1.priority.value == "P0" and t1.sla_breached is True
    t2 = next(t for t in triaged if t.ticket.ticket_id == "T2")
    assert t2.sla_breached is False  # réponse envoyée
    assert triaged[0].ticket.ticket_id == "T1"  # P0 en tête
