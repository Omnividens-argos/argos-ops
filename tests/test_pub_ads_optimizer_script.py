"""Tests du script ``AdsOptimizerScript`` (Pub, archi v2, S3).

Hermétique : campagnes + ``budget.yaml`` sous ``tmp_path``. Vérifie l'écriture
des recos en mémoire, la mise à jour de la jauge et l'armement du breaker.
"""

from __future__ import annotations

from pathlib import Path

from argos_ops.poles.pub import budget
from argos_ops.poles.pub.scripts.ads_optimizer import AdsOptimizerScript


def _write_csv(root: Path, name: str, content: str) -> None:
    d = root / "pub" / "campaigns"
    d.mkdir(parents=True, exist_ok=True)
    (d / name).write_text(content, encoding="utf-8")


async def test_no_campaigns_is_success_noop(tmp_path: Path) -> None:
    result = await AdsOptimizerScript(poles_root=tmp_path).run()
    assert result.status == "success"
    assert result.written == []


async def test_writes_recos_and_updates_gauge_no_trip(tmp_path: Path) -> None:
    budget.set_daily_budget(300.0, poles_root=tmp_path)  # seuil 450/j
    _write_csv(
        tmp_path,
        "2026-06-15-google_search.csv",
        "Campaign,Impressions,Clicks,Cost,Conversions\n"
        "Gaspille,5000,250,500.00,2\n"  # pause (critical)
        "Saine,12000,480,350.00,6\n",  # scale
    )
    result = await AdsOptimizerScript(poles_root=tmp_path, window_days=7).run()
    assert result.status == "success"
    kinds = {r.kind for r in result.written}
    assert "ad_reco" in kinds
    # La reco pause est critique ⇒ fait important + tag d'action lisible par l'agent.
    pause = next(r for r in result.written if "pause" in r.tags)
    assert pause.important is True
    assert "google_search" in pause.tags

    state = budget.load_budget(poles_root=tmp_path)
    assert round(state.spent_per_day_eur, 1) == round(850 / 7, 1)
    assert state.breaker_tripped is False  # 121/j < 450/j


async def test_arms_breaker_on_runaway(tmp_path: Path) -> None:
    budget.set_daily_budget(50.0, poles_root=tmp_path)  # seuil 75/j
    _write_csv(
        tmp_path,
        "2026-06-15-google_search.csv",
        "Campaign,Impressions,Clicks,Cost,Conversions\nGros,5000,250,700.00,10\n",
    )
    result = await AdsOptimizerScript(poles_root=tmp_path, window_days=7).run()
    state = budget.load_budget(poles_root=tmp_path)
    assert state.breaker_tripped is True  # 100/j > 75/j
    # Un fait de synthèse budget_alert est écrit quand le breaker s'arme.
    assert any(r.kind == "budget_alert" for r in result.written)
    assert "BREAKER ARMÉ" in (result.summary or "")


async def test_idempotent_memory(tmp_path: Path) -> None:
    budget.set_daily_budget(300.0, poles_root=tmp_path)
    _write_csv(
        tmp_path,
        "2026-06-15-google_search.csv",
        "Campaign,Impressions,Clicks,Cost,Conversions\nGaspille,5000,250,500.00,2\n",
    )
    first = await AdsOptimizerScript(poles_root=tmp_path).run()
    second = await AdsOptimizerScript(poles_root=tmp_path).run()
    ids_first = {r.id for r in first.written}
    ids_second = {r.id for r in second.written}
    assert ids_first == ids_second  # même corps ⇒ mêmes faits (pas de doublon)
