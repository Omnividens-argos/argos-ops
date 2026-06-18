"""Tests du script ``AdBotScript`` (Pub, archi v2, S3) — pousseur shadow bridé."""

from __future__ import annotations

from pathlib import Path

from argos_ops.poles.pub import applied, budget, creatives
from argos_ops.poles.pub.scripts.ad_bot import AdBotScript


async def test_noop_when_nothing_to_push(tmp_path: Path) -> None:
    result = await AdBotScript(poles_root=tmp_path).run()
    assert result.status == "success"
    assert result.written == []


async def test_publishes_validated_creatives_shadow(tmp_path: Path) -> None:
    creatives.create_creative(platform="google_search", title="Saine", poles_root=tmp_path)
    creatives.set_status("google_search-saine", "validated", poles_root=tmp_path)
    # Une créa draft NE doit PAS être poussée.
    creatives.create_creative(platform="meta", title="Brouillon", poles_root=tmp_path)

    result = await AdBotScript(poles_root=tmp_path).run()
    assert len(result.written) == 1
    rec = result.written[0]
    assert rec.kind == "ad_action"
    assert "shadow" in rec.tags
    assert "publierait" in rec.body


async def test_blocks_when_breaker_tripped(tmp_path: Path) -> None:
    budget.set_daily_budget(50.0, poles_root=tmp_path)
    budget.update_spend({"google_search": 700.0}, window_days=7, poles_root=tmp_path)  # arme
    creatives.create_creative(platform="google_search", title="Saine", poles_root=tmp_path)
    creatives.set_status("google_search-saine", "validated", poles_root=tmp_path)
    # Une reco scale appliquée (augmentatrice de dépense).
    applied.record_applied(
        reco_id="google_search-saine-scale",
        platform="google_search",
        campaign="Saine",
        action="scale",
        eur_delta_week=105.0,
        rationale="r",
        poles_root=tmp_path,
    )
    result = await AdBotScript(poles_root=tmp_path).run()
    # Publication de créa + scale = 2 actions augmentatrices, toutes bloquées.
    assert all("blocked" in r.tags for r in result.written)
    assert all("BLOQUÉ" in r.body for r in result.written)
    assert "bloquée" in (result.summary or "")


async def test_pause_reco_not_blocked_by_breaker(tmp_path: Path) -> None:
    budget.set_daily_budget(50.0, poles_root=tmp_path)
    budget.update_spend({"google_search": 700.0}, window_days=7, poles_root=tmp_path)  # arme
    applied.record_applied(
        reco_id="google_search-gaspille-pause",
        platform="google_search",
        campaign="Gaspille",
        action="pause",
        eur_delta_week=-500.0,
        rationale="r",
        poles_root=tmp_path,
    )
    result = await AdBotScript(poles_root=tmp_path).run()
    # pause réduit la dépense ⇒ jamais bloquée, même breaker armé.
    assert len(result.written) == 1
    assert "shadow" in result.written[0].tags
