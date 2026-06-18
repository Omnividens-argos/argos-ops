"""Tests du ``PubAgent`` (archi v2, S3) — plan borné par le breaker.

Hermétique : ``pole.yaml`` Pub minimal (``reads_cross_pole: [veille]``), mémoire
Veille + propre et ``budget.yaml`` sous ``tmp_path``.
"""

from __future__ import annotations

from pathlib import Path

from argos_ops.poles import memory
from argos_ops.poles.pub import budget
from argos_ops.poles.pub.agent import PubAgent


def _scaffold_pub(root: Path) -> None:
    d = root / "pub"
    d.mkdir(parents=True, exist_ok=True)
    (d / "pole.yaml").write_text(
        "id: pub\nname: Pub\nagent:\n  name: PubAgent\n  skills: []\n"
        "scripts: []\nreads_cross_pole: [veille]\nfront_tools: [memory_table, validation_queue]\n",
        encoding="utf-8",
    )


async def test_skips_on_empty_memory(tmp_path: Path) -> None:
    _scaffold_pub(tmp_path)
    result = await PubAgent(poles_root=tmp_path).run()
    assert result.status == "skipped"


async def test_plans_creative_idea_from_veille(tmp_path: Path) -> None:
    _scaffold_pub(tmp_path)
    await memory.write_memory(
        "veille", "trend_spotter", "Sujet chaud supply-chain", kind="trend", poles_root=tmp_path
    )
    result = await PubAgent(poles_root=tmp_path).run()
    assert result.status == "success"
    assert result.actions
    assert "creative_idea" in result.actions[0]
    assert "veille" in (result.summary or "")


async def test_breaker_freezes_scale_in_plan(tmp_path: Path) -> None:
    _scaffold_pub(tmp_path)
    # Breaker armé.
    budget.set_daily_budget(50.0, poles_root=tmp_path)
    budget.update_spend({"google_search": 700.0}, window_days=7, poles_root=tmp_path)
    # Une reco scale en mémoire propre du pôle.
    await memory.write_memory(
        "pub",
        "ads_optimizer",
        "[google_search] Saine — scaler +30%",
        kind="ad_reco",
        tags=("scale", "google_search", "info"),
        poles_root=tmp_path,
    )
    result = await PubAgent(poles_root=tmp_path).run()
    assert result.status == "success"
    assert "breaker ARMÉ" in (result.summary or "")
    assert any("GELÉ breaker" in a for a in result.actions)


async def test_skips_when_no_actionable_memory(tmp_path: Path) -> None:
    _scaffold_pub(tmp_path)
    # Un fait non routable (ni reco budget, ni sujet Veille publicitaire).
    await memory.write_memory(
        "pub", "ad_bot", "AdBot publierait (shadow)", kind="ad_action", poles_root=tmp_path
    )
    result = await PubAgent(poles_root=tmp_path).run()
    assert result.status == "skipped"
    assert "aucun signal actionnable" in (result.summary or "").lower()
