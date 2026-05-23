"""Tests unitaires de ``argos_ops.agents.contract_generator`` (P22.H)."""

from __future__ import annotations

from pathlib import Path

import yaml

from argos_ops.agents.contract_generator import (
    ContractStats,
    _contract_already_drafted,
    _proposal_is_sent,
    build_contract_embed,
)


def test_proposal_is_sent_requires_status_field(tmp_path: Path) -> None:
    assert not _proposal_is_sent(tmp_path)
    (tmp_path / "status.yaml").write_text(
        yaml.safe_dump({"proposal_status": "drafted"}), encoding="utf-8"
    )
    assert not _proposal_is_sent(tmp_path)


def test_proposal_is_sent_true_when_status_sent(tmp_path: Path) -> None:
    (tmp_path / "status.yaml").write_text(
        yaml.safe_dump({"proposal_status": "sent"}), encoding="utf-8"
    )
    assert _proposal_is_sent(tmp_path)


def test_contract_already_drafted_detects_md_file(tmp_path: Path) -> None:
    assert not _contract_already_drafted(tmp_path)
    (tmp_path / "contract.md").write_text("x", encoding="utf-8")
    assert _contract_already_drafted(tmp_path)


def test_contract_embed_color_yellow_when_drafted() -> None:
    embed = build_contract_embed(ContractStats(deals_seen=1, drafted=1, drafts=["acme-q2"]))
    assert embed.color == 0xF1C40F


def test_contract_embed_color_green_when_none() -> None:
    embed = build_contract_embed(ContractStats(deals_seen=0, drafted=0))
    assert embed.color == 0x2ECC71
