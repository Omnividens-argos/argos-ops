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


# =============================================================================
# Cerveau (Axe 2) — relance recommandée par deal à risque
# =============================================================================
def _flag(deal_id: str = "d1", notes: str | None = "Attend un devis pour 50 scans"):
    from argos_ops.sales.models import DealStalledFlag

    deal = Deal(
        deal_id=deal_id,
        company="Acme",
        stage=DealStage.PROPOSAL_SENT,
        amount_eur=4200,
        last_activity_at=TODAY - timedelta(days=20),
        notes=notes,
    )
    return DealStalledFlag(
        deal=deal,
        days_since_activity=20,
        risk_score=72,
        is_stalled=True,
        reason="stalled 20j",
    )


def test_build_actions_prompt_includes_notes_and_forbids_promises() -> None:
    from argos_ops.agents.deal_risk_scorer import build_actions_prompt

    prompt = build_actions_prompt([_flag("DEAL-1", notes="Marc revient mardi avec son board")])
    assert "deal_id: DEAL-1" in prompt
    assert "Marc revient mardi avec son board" in prompt  # les notes sont injectées
    assert "ne promets RIEN" in prompt
    assert '"actions"' in prompt


def test_parse_brain_actions_validates_entries() -> None:
    from argos_ops.agents.deal_risk_scorer import parse_brain_actions

    data = {
        "actions": [
            {"deal_id": "d1", "action": "Envoyer le devis 50 scans aujourd'hui et caler un call."},
            {"deal_id": "inconnu", "action": "x" * 50},
            {"deal_id": "d2", "action": "court"},  # < 20 chars
            {"deal_id": "d3", "action": "x" * 500},  # > 220 chars
        ]
    }
    out = parse_brain_actions(data, known_ids={"d1", "d2", "d3"})
    assert set(out) == {"d1"}
    assert parse_brain_actions({"oops": 1}, known_ids={"d1"}) == {}


def test_risk_embed_shows_action_under_top_risk() -> None:
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
    embed = build_risk_embed(report, actions={"c": "Relancer la décision du board sous 48h."})
    block = next(f.value for f in embed.fields if f.name == "Top risque")
    assert "→ Relancer la décision du board sous 48h." in block


def test_recommend_actions_disabled_returns_empty(monkeypatch) -> None:
    import asyncio

    from argos_ops.agents import deal_risk_scorer as drs
    from argos_ops.brain import BrainAnswer

    async def fake_think(prompt: str, **_: object) -> BrainAnswer:
        return BrainAnswer(ok=False, data=None, raw=None, engine="disabled", error="off")

    monkeypatch.setattr(drs, "think_json", fake_think)
    actions, engine = asyncio.run(drs.recommend_actions([_flag("d1")]))
    assert actions == {} and engine == "disabled"


def test_recommend_actions_happy_path(monkeypatch) -> None:
    import asyncio

    from argos_ops.agents import deal_risk_scorer as drs
    from argos_ops.brain import BrainAnswer

    async def fake_think(prompt: str, **_: object) -> BrainAnswer:
        assert "deal_id: d1" in prompt
        return BrainAnswer(
            ok=True,
            data={"actions": [{"deal_id": "d1", "action": "Envoyer le devis 50 scans ce jour."}]},
            raw="{}",
            engine="claude",
        )

    monkeypatch.setattr(drs, "think_json", fake_think)
    actions, engine = asyncio.run(drs.recommend_actions([_flag("d1")]))
    assert engine == "claude"
    assert actions["d1"].startswith("Envoyer le devis")
