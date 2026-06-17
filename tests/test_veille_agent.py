"""Tests du ``VeilleAgent`` (archi v2, S1) — synthèse depuis la mémoire de pôle.

Hermétique : on scaffold un ``pole.yaml`` Veille minimal et la mémoire de
quelques scripts sous ``tmp_path``, puis on vérifie que l'agent lit et
synthétise (sans cross-pôle).
"""

from __future__ import annotations

from pathlib import Path

from argos_ops.poles import memory
from argos_ops.poles.veille.agent import VeilleAgent


def _scaffold_veille(root: Path) -> None:
    d = root / "veille"
    d.mkdir(parents=True, exist_ok=True)
    (d / "pole.yaml").write_text(
        "id: veille\nname: Veille\nagent:\n  name: VeilleAgent\n  skills: []\n"
        "scripts:\n  - id: trend_spotter\n  - id: cve_monitor\n"
        "reads_cross_pole: []\nfront_tools: [memory_table, alert_card]\n",
        encoding="utf-8",
    )


async def test_agent_skips_on_empty_memory(tmp_path: Path) -> None:
    _scaffold_veille(tmp_path)
    result = await VeilleAgent(poles_root=tmp_path).run()
    assert result.status == "skipped"


async def test_agent_synthesizes_insights(tmp_path: Path) -> None:
    _scaffold_veille(tmp_path)
    await memory.write_memory(
        "veille",
        "trend_spotter",
        "Sujet chaud : Ivanti",
        kind="trend",
        tags=("cyber",),
        poles_root=tmp_path,
    )
    await memory.write_memory(
        "veille",
        "cve_monitor",
        "CVE-2026-1 critique sur nginx",
        kind="cve",
        tags=("cve", "critical"),
        important=True,
        poles_root=tmp_path,
    )

    result = await VeilleAgent(poles_root=tmp_path).run()

    assert result.status == "success"
    assert result.actions  # au moins un insight
    # L'insight critique (cve) doit être routé vers la vente et listé en premier.
    assert "vente" in result.actions[0]
    assert "critical" in result.actions[0]


async def test_agent_does_not_read_cross_pole(tmp_path: Path) -> None:
    _scaffold_veille(tmp_path)
    # Mémoire d'un AUTRE pôle : ne doit pas remonter dans le contexte Veille.
    (tmp_path / "marketing").mkdir(parents=True, exist_ok=True)
    (tmp_path / "marketing" / "pole.yaml").write_text(
        "id: marketing\nname: Marketing\nagent:\n  name: MarketingAgent\n"
        "scripts: []\nreads_cross_pole: []\nfront_tools: []\n",
        encoding="utf-8",
    )
    await memory.write_memory("marketing", "x", "fait marketing", kind="note", poles_root=tmp_path)
    await memory.write_memory(
        "veille", "trend_spotter", "Sujet veille", kind="trend", poles_root=tmp_path
    )

    agent = VeilleAgent(poles_root=tmp_path)
    context = await agent.load_context()
    assert "marketing" not in context.cross_pole
    assert "trend_spotter" in context.own
