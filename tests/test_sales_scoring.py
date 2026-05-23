"""Tests unitaires de ``argos_ops.sales.scoring`` (P22.H Sales Sprint 3)."""

from __future__ import annotations

from datetime import date, timedelta

from argos_ops.sales.models import Deal, DealStage
from argos_ops.sales.scoring import STALLED_THRESHOLD_DAYS, score_deal_risk

TODAY = date(2026, 5, 23)


def _deal(stage: DealStage, days_ago: int, amount: int = 1000) -> Deal:
    return Deal(
        deal_id="demo",
        company="Acme",
        stage=stage,
        amount_eur=amount,
        last_activity_at=TODAY - timedelta(days=days_ago),
    )


def test_won_returns_zero_risk_not_stalled() -> None:
    flag = score_deal_risk(_deal(DealStage.WON, 100), today=TODAY)
    assert flag.risk_score == 0
    assert not flag.is_stalled


def test_lost_returns_zero_risk_not_stalled() -> None:
    flag = score_deal_risk(_deal(DealStage.LOST, 100), today=TODAY)
    assert flag.risk_score == 0
    assert not flag.is_stalled


def test_discovery_below_threshold_not_stalled() -> None:
    flag = score_deal_risk(_deal(DealStage.DISCOVERY, 5), today=TODAY)
    assert not flag.is_stalled


def test_discovery_above_threshold_is_stalled() -> None:
    flag = score_deal_risk(_deal(DealStage.DISCOVERY, 20), today=TODAY)
    assert flag.is_stalled
    assert flag.days_since_activity == 20


def test_demo_scheduled_has_shortest_threshold() -> None:
    assert STALLED_THRESHOLD_DAYS[DealStage.DEMO_SCHEDULED] == 7
    flag = score_deal_risk(_deal(DealStage.DEMO_SCHEDULED, 10), today=TODAY)
    assert flag.is_stalled


def test_contract_sent_has_largest_threshold() -> None:
    assert STALLED_THRESHOLD_DAYS[DealStage.CONTRACT_SENT] == 30
    flag = score_deal_risk(_deal(DealStage.CONTRACT_SENT, 20), today=TODAY)
    assert not flag.is_stalled


def test_high_amount_increases_risk() -> None:
    small = score_deal_risk(_deal(DealStage.PROPOSAL_SENT, 10, amount=300), today=TODAY)
    big = score_deal_risk(_deal(DealStage.PROPOSAL_SENT, 10, amount=8000), today=TODAY)
    assert big.risk_score > small.risk_score


def test_risk_score_capped_at_100() -> None:
    flag = score_deal_risk(_deal(DealStage.PROPOSAL_SENT, 200, amount=10000), today=TODAY)
    assert flag.risk_score == 100


def test_future_activity_clamps_to_zero_days() -> None:
    flag = score_deal_risk(_deal(DealStage.DISCOVERY, -5), today=TODAY)
    assert flag.days_since_activity == 0
