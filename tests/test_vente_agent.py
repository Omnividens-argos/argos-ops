"""Tests du ``VenteAgent`` (archi v2, S4) — plan cross-pôle borné par Bloctel."""

from __future__ import annotations

from pathlib import Path

from argos_ops.poles import memory
from argos_ops.poles.vente.agent import VenteAgent

_POLE_YAML = (
    "id: vente\nname: Vente\nagent:\n  name: VenteAgent\n  skills: []\n"
    "scripts: []\nreads_cross_pole: [veille, marketing]\nfront_tools: [memory_table]\n"
)


def _scaffold(root: Path) -> None:
    d = root / "vente"
    d.mkdir(parents=True, exist_ok=True)
    (d / "pole.yaml").write_text(_POLE_YAML, encoding="utf-8")


def _bloctel_match(root: Path) -> None:
    """Arme le gel Bloctel (téléphone opposé) sous ``root``."""
    comp = root / "vente" / "compliance"
    (comp / "bloctel").mkdir(parents=True, exist_ok=True)
    (comp / "lead_phones.csv").write_text("identifier,phone\nl,+33611223344\n", encoding="utf-8")
    (comp / "bloctel" / "bloctel_2026-06.txt").write_text("+33611223344\n", encoding="utf-8")


async def test_skips_on_empty_memory(tmp_path: Path) -> None:
    _scaffold(tmp_path)
    result = await VenteAgent(poles_root=tmp_path).run()
    assert result.status == "skipped"


async def test_plans_from_own_and_cross_pole(tmp_path: Path) -> None:
    _scaffold(tmp_path)
    # Fait propre : ticket P0 ; cross-pôle Veille : signal d'achat.
    await memory.write_memory(
        "vente",
        "escalation_router",
        "[P0] prod down",
        kind="ticket",
        tags=("P0", "critical"),
        important=True,
        poles_root=tmp_path,
    )
    await memory.write_memory(
        "veille",
        "intent_signals",
        "breach chez prospect-x.fr",
        kind="intent_signal",
        tags=("intent",),
        important=True,
        poles_root=tmp_path,
    )
    result = await VenteAgent(poles_root=tmp_path).run()
    assert result.status == "success"
    assert any("ticket" in a for a in result.actions)
    assert "veille" in (result.summary or "")


async def test_bloctel_freezes_outreach(tmp_path: Path) -> None:
    _scaffold(tmp_path)
    _bloctel_match(tmp_path)
    await memory.write_memory(
        "vente",
        "lead_enricher",
        "Lead qualifié Marc",
        kind="lead",
        tags=("marc", "qualified"),
        important=True,
        poles_root=tmp_path,
    )
    result = await VenteAgent(poles_root=tmp_path).run()
    assert result.status == "success"
    assert "GELÉ Bloctel" in (result.summary or "") or any(
        "GELÉ Bloctel" in a for a in result.actions
    )


async def test_skips_when_no_actionable(tmp_path: Path) -> None:
    _scaffold(tmp_path)
    await memory.write_memory(
        "vente", "prospect_miner", "nouveau prospect", kind="prospect", poles_root=tmp_path
    )
    result = await VenteAgent(poles_root=tmp_path).run()
    assert result.status == "skipped"
    assert "aucune action" in (result.summary or "").lower()
