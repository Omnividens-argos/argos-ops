"""Tests du ``MarketingAgent`` (archi v2, S2) — recommandations depuis Veille + propre.

Hermétique : ``pole.yaml`` Marketing minimal (``reads_cross_pole: [veille]``),
mémoire Veille + propre sous ``tmp_path``.
"""

from __future__ import annotations

from pathlib import Path

from argos_ops.poles import memory
from argos_ops.poles.marketing.agent import MarketingAgent


def _scaffold_marketing(root: Path) -> None:
    d = root / "marketing"
    d.mkdir(parents=True, exist_ok=True)
    (d / "pole.yaml").write_text(
        "id: marketing\nname: Marketing\nagent:\n  name: MarketingAgent\n  skills: []\n"
        "scripts: []\nreads_cross_pole: [veille]\nfront_tools: [memory_table, validation_queue]\n",
        encoding="utf-8",
    )


async def test_skips_on_empty_memory(tmp_path: Path) -> None:
    _scaffold_marketing(tmp_path)
    result = await MarketingAgent(poles_root=tmp_path).run()
    assert result.status == "skipped"


async def test_recommends_from_veille_cross_pole(tmp_path: Path) -> None:
    _scaffold_marketing(tmp_path)
    await memory.write_memory(
        "veille",
        "breach_watcher",
        "Fuite massive chez un fournisseur",
        kind="breach",
        tags=("critical",),
        poles_root=tmp_path,
    )
    await memory.write_memory(
        "veille", "trend_spotter", "Sujet chaud supply-chain", kind="trend", poles_root=tmp_path
    )
    # Mémoire propre non éditorialisable : ne doit pas générer de reco.
    await memory.write_memory(
        "marketing", "content_bot", "Publié sur LinkedIn", kind="publication", poles_root=tmp_path
    )

    result = await MarketingAgent(poles_root=tmp_path).run()
    assert result.status == "success"
    assert result.actions
    # Le breach critique est routé en premier vers des canaux infosec.
    assert "critical" in result.actions[0]
    assert "Veille incluse" in (result.summary or "")


async def test_skips_when_only_non_routable_memory(tmp_path: Path) -> None:
    _scaffold_marketing(tmp_path)
    await memory.write_memory(
        "marketing",
        "social_analytics",
        "Engagement linkedin 7j",
        kind="engagement",
        poles_root=tmp_path,
    )
    result = await MarketingAgent(poles_root=tmp_path).run()
    assert result.status == "skipped"
    assert "aucun signal" in (result.summary or "").lower()
