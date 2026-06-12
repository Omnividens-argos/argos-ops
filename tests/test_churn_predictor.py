"""Tests unitaires de ``argos_ops.agents.churn_predictor`` (P22.G)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import yaml

from argos_ops.agents.churn_predictor import (
    ChurnReport,
    _persist_snapshot,
    build_churn_embed,
)
from argos_ops.cs.models import ChurnSignal


def test_embed_red_when_urgent() -> None:
    signals = [ChurnSignal("acme", 85, ["inactif 60j", "NPS détracteur"])]
    report = ChurnReport(customers_seen=4, at_risk=signals, urgent=signals)
    assert build_churn_embed(report).color == 0xE74C3C


def test_embed_yellow_when_at_risk_not_urgent() -> None:
    signals = [ChurnSignal("acme", 35, ["sous-utilisation"])]
    report = ChurnReport(customers_seen=4, at_risk=signals, urgent=[])
    assert build_churn_embed(report).color == 0xF1C40F


def test_embed_green_when_clean() -> None:
    report = ChurnReport(customers_seen=4)
    assert build_churn_embed(report).color == 0x2ECC71


def test_persist_snapshot_writes_yaml(tmp_path: Path) -> None:
    signals = [ChurnSignal("acme", 75, ["inactif 45j", "tickets 30j élevés"])]
    path = tmp_path / "at_risk_2026-05-23.yaml"
    _persist_snapshot(path, signals, day=date(2026, 5, 23))
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert raw["snapshot_date"] == "2026-05-23"
    assert raw["at_risk"][0]["customer_id"] == "acme"
    assert raw["at_risk"][0]["risk_score"] == 75


# =============================================================================
# Cerveau (Axe 2) — action recommandée par compte à risque
# =============================================================================
def test_build_actions_prompt_lists_accounts_and_forbids_promises() -> None:
    from argos_ops.agents.churn_predictor import build_actions_prompt
    from argos_ops.cs.models import ChurnSignal

    signals = [
        ChurnSignal(customer_id="acme-sa", risk_score=75, signals=["inactif depuis 35j"]),
        ChurnSignal(customer_id="beta-io", risk_score=40, signals=["NPS détracteur (4/10)"]),
    ]
    prompt = build_actions_prompt(signals)
    assert "customer_id: acme-sa" in prompt and "customer_id: beta-io" in prompt
    assert "inactif depuis 35j" in prompt
    assert "ne promets RIEN" in prompt
    assert '"actions"' in prompt


def test_parse_brain_actions_validates_entries() -> None:
    from argos_ops.agents.churn_predictor import parse_brain_actions

    data = {
        "actions": [
            {
                "customer_id": "acme-sa",
                "action": "Appeler le RSSI pour rejouer le cas d'usage scan CI.",
            },
            {"customer_id": "inconnu", "action": "x" * 50},
            {"customer_id": "beta-io", "action": "court"},  # < 20 chars
            {"customer_id": "gamma", "action": "x" * 500},  # > 220 chars
        ]
    }
    out = parse_brain_actions(data, known_ids={"acme-sa", "beta-io", "gamma"})
    assert set(out) == {"acme-sa"}
    assert parse_brain_actions({"oops": 1}, known_ids={"acme-sa"}) == {}


def test_persist_snapshot_includes_actions_and_engine(tmp_path: Path) -> None:
    from argos_ops.agents.churn_predictor import _persist_snapshot
    from argos_ops.cs.models import ChurnSignal

    signals = [
        ChurnSignal(customer_id="acme-sa", risk_score=75, signals=["inactif 35j"]),
        ChurnSignal(customer_id="beta-io", risk_score=40, signals=["NPS 4"]),
    ]
    path = tmp_path / "at_risk_2026-06-12.yaml"
    _persist_snapshot(
        path,
        signals,
        day=date(2026, 6, 12),
        actions={"acme-sa": "Appeler le RSSI sous 48h pour réactiver le scan CI."},
        engine="claude",
    )
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert raw["actions_engine"] == "claude"
    by_id = {e["customer_id"]: e for e in raw["at_risk"]}
    assert "recommended_action" in by_id["acme-sa"]
    assert "recommended_action" not in by_id["beta-io"]  # pas d'action → pas de clé


def test_build_churn_embed_shows_action_for_urgent() -> None:
    from argos_ops.agents.churn_predictor import ChurnReport, build_churn_embed
    from argos_ops.cs.models import ChurnSignal

    urgent = ChurnSignal(customer_id="acme-sa", risk_score=75, signals=["inactif 35j"])
    report = ChurnReport(customers_seen=1, at_risk=[urgent], urgent=[urgent])
    embed = build_churn_embed(report, actions={"acme-sa": "Appeler le RSSI sous 48h."})
    block = next(f.value for f in embed.fields if f.name == "Action proactive 48h")
    assert "→ Appeler le RSSI sous 48h." in block


def test_recommend_actions_disabled_returns_empty(monkeypatch) -> None:
    import asyncio

    from argos_ops.agents import churn_predictor as cp
    from argos_ops.brain import BrainAnswer
    from argos_ops.cs.models import ChurnSignal

    async def fake_think(prompt: str, **_: object) -> BrainAnswer:
        return BrainAnswer(ok=False, data=None, raw=None, engine="disabled", error="off")

    monkeypatch.setattr(cp, "think_json", fake_think)
    signals = [ChurnSignal(customer_id="acme-sa", risk_score=75, signals=["inactif"])]
    actions, engine = asyncio.run(cp.recommend_actions(signals))
    assert actions == {} and engine == "disabled"
