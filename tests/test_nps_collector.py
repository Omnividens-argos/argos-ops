"""Tests unitaires de ``argos_ops.agents.nps_collector`` (P22.G)."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import yaml

from argos_ops.agents.nps_collector import (
    NPSStats,
    _draft_nps,
    build_nps_embed,
    needs_post_onboarding_nps,
    needs_post_renew_nps,
)
from argos_ops.cs.models import Customer, CustomerPlan, CustomerUsage


def _customer(**overrides: object) -> Customer:
    base: dict[str, object] = {
        "customer_id": "acme-sa",
        "name": "Acme SA",
        "contact_email": "marc@acme.fr",
        "contact_name": "Marc Dupont",
        "plan": CustomerPlan.PRO,
        "signup_date": date(2026, 1, 1),
        "usage": CustomerUsage(),
    }
    base.update(overrides)
    return Customer(**base)  # type: ignore[arg-type]


def test_needs_post_onboarding_when_done_14d_ago_and_never_collected() -> None:
    today = date.today()
    customer = _customer(onboarding_done_at=today - timedelta(days=20))
    assert needs_post_onboarding_nps(customer, today=today) is True


def test_does_not_need_onboarding_nps_when_already_collected() -> None:
    today = date.today()
    customer = _customer(
        onboarding_done_at=today - timedelta(days=20),
        last_nps_at=today - timedelta(days=5),
        last_nps=9,
    )
    assert needs_post_onboarding_nps(customer, today=today) is False


def test_needs_renew_nps_when_renew_21d_ago_no_recent_collect() -> None:
    today = date.today()
    customer = _customer(
        last_renew_at=today - timedelta(days=25),
        last_nps_at=today - timedelta(days=200),  # ancien NPS pré-renew
    )
    assert needs_post_renew_nps(customer, today=today) is True


def test_does_not_need_renew_nps_too_soon() -> None:
    today = date.today()
    customer = _customer(last_renew_at=today - timedelta(days=10))
    assert needs_post_renew_nps(customer, today=today) is False


def test_draft_nps_writes_md(tmp_path: Path) -> None:
    customer = _customer()
    path = _draft_nps(customer, "onboarding_done", tmp_path)
    assert path.exists()
    content = path.read_text(encoding="utf-8")
    head = content.split("---\n", 2)
    front = yaml.safe_load(head[1])
    assert front["customer_id"] == "acme-sa"
    assert front["reason"] == "onboarding_done"
    assert "recommanderiez-vous" in content


def test_build_nps_embed_yellow_when_drafted() -> None:
    embed = build_nps_embed(NPSStats(customers_seen=2, drafts_created=2, drafts=["a", "b"]))
    assert embed.color == 0xF1C40F
