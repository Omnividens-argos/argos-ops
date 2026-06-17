"""Tests pipeline du pôle Vente (archi v2, S4) — chargement + scoring + stalled."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from argos_ops.poles.vente import pipeline


def _write_pipe(root: Path, body: str) -> None:
    d = root / "vente" / "deals"
    d.mkdir(parents=True, exist_ok=True)
    (d / "pipe.yaml").write_text(body, encoding="utf-8")


def test_load_deals_empty(tmp_path: Path) -> None:
    assert pipeline.load_deals(poles_root=tmp_path) == []


def test_load_and_score(tmp_path: Path) -> None:
    _write_pipe(
        tmp_path,
        "deals:\n"
        "  - deal_id: D1\n    company: Acme\n    stage: proposal_sent\n"
        "    amount_eur: 6000\n    last_activity_at: '2026-05-01'\n"
        "  - deal_id: D2\n    company: Beta\n    stage: discovery\n"
        "    amount_eur: 1000\n    last_activity_at: '2026-06-16'\n",
    )
    deals = pipeline.load_deals(poles_root=tmp_path)
    assert len(deals) == 2
    flags = pipeline.score_pipeline(deals, today=date(2026, 6, 17))
    # Trié par risque décroissant : D1 (vieux + gros + proposal) en tête.
    assert flags[0].deal.deal_id == "D1"
    assert flags[0].is_stalled is True
    stalled = pipeline.stalled_active(flags)
    assert [f.deal.deal_id for f in stalled] == ["D1"]


def test_pipeline_value_excludes_won_lost(tmp_path: Path) -> None:
    _write_pipe(
        tmp_path,
        "deals:\n"
        "  - deal_id: A\n    company: A\n    stage: won\n    amount_eur: 9999\n    last_activity_at: '2026-06-01'\n"
        "  - deal_id: B\n    company: B\n    stage: discovery\n    amount_eur: 1500\n    last_activity_at: '2026-06-16'\n",
    )
    deals = pipeline.load_deals(poles_root=tmp_path)
    assert pipeline.pipeline_value_eur(deals) == 1500


def test_bad_stage_ignored(tmp_path: Path) -> None:
    _write_pipe(
        tmp_path,
        "deals:\n"
        "  - deal_id: X\n    company: X\n    stage: not_a_stage\n    amount_eur: 1\n    last_activity_at: '2026-06-01'\n"
        "  - deal_id: Y\n    company: Y\n    stage: discovery\n    amount_eur: 1\n    last_activity_at: '2026-06-16'\n",
    )
    deals = pipeline.load_deals(poles_root=tmp_path)
    assert [d.deal_id for d in deals] == ["Y"]
