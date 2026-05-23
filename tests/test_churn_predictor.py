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
