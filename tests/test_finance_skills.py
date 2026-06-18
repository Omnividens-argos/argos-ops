"""Tests de la banque de skills de l'agent Finance (archi v2, S5)."""

from __future__ import annotations

from argos_ops.poles.finance.skills import (
    KNOWN_ROLES,
    load_skill_bank,
    validate_skill_bank,
)


def test_real_skill_bank_is_consistent() -> None:
    """La banque committée doit être saine (parité fiches ↔ pole.yaml, rôles connus)."""
    assert validate_skill_bank() == []


def test_real_skill_bank_loads_eight() -> None:
    bank = load_skill_bank()
    assert len(bank) == 8
    assert all(s.role in KNOWN_ROLES for s in bank)
    assert all(s.summary for s in bank)  # corps non vide


def test_known_roles() -> None:
    assert {"billing", "fiscal", "compliance", "treasury"} == KNOWN_ROLES
