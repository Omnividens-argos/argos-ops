"""Tests unitaires de ``argos_ops.agents.review_bot`` (P22.G)."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import yaml

from argos_ops.agents.review_bot import (
    ReviewStats,
    _draft_review_request,
    build_review_embed,
    is_review_eligible,
)
from argos_ops.cs.models import Customer, CustomerPlan, CustomerUsage


def _customer(**overrides: object) -> Customer:
    base: dict[str, object] = dict(
        customer_id="acme-sa",
        name="Acme SA",
        contact_email="marc@acme.fr",
        contact_name="Marc Dupont",
        plan=CustomerPlan.PRO,
        signup_date=date(2026, 1, 1),
        onboarding_done_at=date.today() - timedelta(days=45),
        last_nps=9,
        usage=CustomerUsage(),
    )
    base.update(overrides)
    return Customer(**base)  # type: ignore[arg-type]


def test_eligible_when_promoter_onboarded_45d_ago() -> None:
    customer = _customer()
    assert is_review_eligible(customer, today=date.today()) is True


def test_not_eligible_when_already_reviewed() -> None:
    customer = _customer(last_review_at=date.today() - timedelta(days=10))
    assert is_review_eligible(customer, today=date.today()) is False


def test_not_eligible_when_detractor() -> None:
    customer = _customer(last_nps=5)
    assert is_review_eligible(customer, today=date.today()) is False


def test_not_eligible_when_no_nps() -> None:
    customer = _customer(last_nps=None)
    assert is_review_eligible(customer, today=date.today()) is False


def test_not_eligible_too_early() -> None:
    customer = _customer(onboarding_done_at=date.today() - timedelta(days=20))
    assert is_review_eligible(customer, today=date.today()) is False


def test_draft_review_writes_md(tmp_path: Path) -> None:
    customer = _customer()
    path = _draft_review_request(customer, tmp_path)
    assert path.exists()
    content = path.read_text(encoding="utf-8")
    front = yaml.safe_load(content.split("---\n", 2)[1])
    assert front["customer_id"] == "acme-sa"
    assert front["nps_at_request"] == 9
    assert "G2" in content
    assert "Capterra" in content


def test_embed_yellow_when_drafts() -> None:
    embed = build_review_embed(ReviewStats(customers_seen=3, drafts_created=1, drafts=["a"]))
    assert embed.color == 0xF1C40F
