"""Tests unitaires de ``argos_ops.agents.deal_risk_scorer`` (P22.H)."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import yaml

from argos_ops.agents.deal_risk_scorer import (
    _load_pipe,
    build_risk_embed,
    build_risk_report,
)
from argos_ops.sales.models import Deal, DealStage

TODAY = date(2026, 5, 23)


def _deal_dict(stage: str, days_ago: int, amount: int = 1000, deal_id: str = "d1") -> dict:
    return {
        "deal_id": deal_id,
        "company": "Acme",
        "stage": stage,
        "amount_eur": amount,
        "last_activity_at": (TODAY - timedelta(days=days_ago)).isoformat(),
        "owner": "founder",
    }


def test_load_pipe_parses_yaml(tmp_path: Path) -> None:
    path = tmp_path / "pipe.yaml"
    path.write_text(
        yaml.safe_dump({"deals": [_deal_dict("discovery", 5)]}),
        encoding="utf-8",
    )
    deals = _load_pipe(path)
    assert len(deals) == 1
    assert isinstance(deals[0], Deal)
    assert deals[0].stage == DealStage.DISCOVERY


def test_load_pipe_empty_when_missing(tmp_path: Path) -> None:
    assert _load_pipe(tmp_path / "absent.yaml") == []


def test_build_risk_report_counts_buckets() -> None:
    deals = [
        Deal(
            deal_id="a",
            company="A",
            stage=DealStage.WON,
            amount_eur=1000,
            last_activity_at=TODAY - timedelta(days=30),
        ),
        Deal(
            deal_id="b",
            company="B",
            stage=DealStage.LOST,
            amount_eur=2000,
            last_activity_at=TODAY - timedelta(days=60),
        ),
        Deal(
            deal_id="c",
            company="C",
            stage=DealStage.PROPOSAL_SENT,
            amount_eur=4200,
            last_activity_at=TODAY - timedelta(days=20),
        ),
        Deal(
            deal_id="d",
            company="D",
            stage=DealStage.DISCOVERY,
            amount_eur=500,
            last_activity_at=TODAY - timedelta(days=3),
        ),
    ]
    report = build_risk_report(deals, today=TODAY)
    assert report.total == 4
    assert report.won == 1
    assert report.lost == 1
    assert report.active == 2
    assert report.stalled == 1  # only "c" is past threshold
    assert report.top_risk[0].deal.deal_id == "c"


def test_risk_embed_orange_when_stalled() -> None:
    deals = [
        Deal(
            deal_id="c",
            company="C",
            stage=DealStage.PROPOSAL_SENT,
            amount_eur=4200,
            last_activity_at=TODAY - timedelta(days=30),
        ),
    ]
    report = build_risk_report(deals, today=TODAY)
    embed = build_risk_embed(report)
    assert embed.color == 0xE67E22


def test_risk_embed_green_when_nothing() -> None:
    report = build_risk_report([], today=TODAY)
    embed = build_risk_embed(report)
    assert embed.color == 0x2ECC71
