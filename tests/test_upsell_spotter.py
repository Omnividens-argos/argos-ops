"""Tests unitaires de ``argos_ops.agents.upsell_spotter`` (P22.G)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import yaml

from argos_ops.agents.upsell_spotter import (
    UpsellReport,
    _persist_snapshot,
    build_upsell_embed,
)
from argos_ops.cs.models import CustomerPlan, UpsellCandidate


def test_build_upsell_embed_green_when_no_candidates() -> None:
    embed = build_upsell_embed(UpsellReport(candidates=[], customers_seen=4))
    assert embed.color == 0x2ECC71


def test_build_upsell_embed_yellow_when_candidates() -> None:
    candidates = [
        UpsellCandidate(
            customer_id="acme-sa",
            usage_ratio=0.9,
            suggested_plan=CustomerPlan.ENTERPRISE,
            reason="usage saturé",
        )
    ]
    embed = build_upsell_embed(UpsellReport(candidates=candidates, customers_seen=2))
    assert embed.color == 0xF1C40F


def test_persist_snapshot_writes_yaml(tmp_path: Path) -> None:
    candidates = [
        UpsellCandidate(
            customer_id="acme-sa",
            usage_ratio=0.85,
            suggested_plan=CustomerPlan.PRO,
            reason="usage 85% sur starter",
        )
    ]
    path = tmp_path / "candidates_2026-05-23.yaml"
    _persist_snapshot(path, candidates, day=date(2026, 5, 23))
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert raw["snapshot_date"] == "2026-05-23"
    assert raw["candidates"][0]["suggested_plan"] == "pro"
    assert raw["candidates"][0]["usage_ratio"] == 0.85
