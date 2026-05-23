"""Tests unitaires de ``argos_ops.agents.onboarding_bot`` (P22.G)."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import yaml

from argos_ops.agents.onboarding_bot import (
    OnboardingStats,
    _draft_onboarding,
    _due_steps,
    build_onboarding_embed,
)
from argos_ops.cs.models import Customer, CustomerPlan, CustomerUsage


def _customer(signup_offset_days: int) -> Customer:
    return Customer(
        customer_id="acme-sa",
        name="Acme SA",
        contact_email="marc@acme.fr",
        contact_name="Marc Dupont",
        plan=CustomerPlan.PRO,
        signup_date=date.today() - timedelta(days=signup_offset_days),
        usage=CustomerUsage(),
    )


def test_due_steps_includes_j7_after_a_week() -> None:
    customer = _customer(signup_offset_days=8)
    assert 0 in _due_steps(customer, today=date.today())
    assert 7 in _due_steps(customer, today=date.today())
    assert 30 not in _due_steps(customer, today=date.today())


def test_due_steps_all_three_after_a_month() -> None:
    customer = _customer(signup_offset_days=31)
    assert _due_steps(customer, today=date.today()) == [0, 7, 30]


def test_draft_onboarding_writes_md_with_frontmatter(tmp_path: Path) -> None:
    customer = _customer(signup_offset_days=0)
    draft = _draft_onboarding(customer, step=0, drafts_dir=tmp_path)
    assert draft.exists()
    content = draft.read_text(encoding="utf-8")
    assert "Bienvenue chez Argos" in content
    assert "marc@acme.fr" in content
    head = content.split("---\n", 2)
    front = yaml.safe_load(head[1])
    assert front["customer_id"] == "acme-sa"
    assert front["step"] == "J+0"
    assert front["status"] == "drafted"


def test_build_onboarding_embed_green_when_no_drafts() -> None:
    embed = build_onboarding_embed(OnboardingStats(customers_seen=3, drafts_created=0))
    assert embed.color == 0x2ECC71


def test_build_onboarding_embed_yellow_when_drafted() -> None:
    embed = build_onboarding_embed(
        OnboardingStats(customers_seen=2, drafts_created=1, drafts=["acme-J0.md"])
    )
    assert embed.color == 0xF1C40F
