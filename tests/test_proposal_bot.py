"""Tests unitaires de ``argos_ops.agents.proposal_bot`` (P22.H)."""

from __future__ import annotations

from pathlib import Path

import yaml

from argos_ops.agents.proposal_bot import (
    ProposalStats,
    _is_drafted,
    _load_context,
    _write_status,
    build_proposal_embed,
)


def _ctx_yaml(deal_id: str = "acme-q2-2026") -> dict:
    return {
        "deal_id": deal_id,
        "company": "Acme SA",
        "contact_name": "Marc Dupont",
        "contact_email": "marc@acme.fr",
        "siret": "12345678900012",
        "plan": "Argos Pro",
        "monthly_price_eur": 350,
        "setup_fee_eur": 500,
        "discount_percent": 10,
        "contract_duration_months": 12,
        "issue_date": "2026-05-23",
        "validity_days": 30,
    }


def test_load_context_parses_yaml(tmp_path: Path) -> None:
    ctx_path = tmp_path / "context.yaml"
    ctx_path.write_text(yaml.safe_dump(_ctx_yaml()), encoding="utf-8")
    ctx = _load_context(ctx_path)
    assert ctx.deal_id == "acme-q2-2026"
    assert ctx.monthly_price_eur == 350
    assert ctx.discount_percent == 10


def test_is_drafted_false_when_no_status(tmp_path: Path) -> None:
    assert not _is_drafted(tmp_path)


def test_is_drafted_true_when_status_set(tmp_path: Path) -> None:
    _write_status(tmp_path, pdf_ok=False)
    assert _is_drafted(tmp_path)


def test_proposal_embed_green_when_nothing_drafted() -> None:
    embed = build_proposal_embed(ProposalStats(deals_seen=2, already_drafted=2))
    assert embed.color == 0x2ECC71


def test_proposal_embed_yellow_when_drafted() -> None:
    embed = build_proposal_embed(ProposalStats(deals_seen=2, drafted=2, drafts=["a", "b"]))
    assert embed.color == 0xF1C40F
