"""Tests unitaires AdBot live (P12.B).

Couvre :
- load_recommendations() : parse YAML d'ads-optimizer
- AdBotLive.run() : cap budget + shadow vs live + archivage
- build_ad_embed() : couleurs selon mode et blocked
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from argos_ops.agents.ad_bot_live import (
    AdAction,
    AdRunStats,
    build_ad_embed,
    load_recommendations,
)
from argos_ops.notifications.discord import GREEN, ORANGE, YELLOW


def _write_reco(dir_: Path, name: str, actions: list[dict[str, object]]) -> Path:
    dir_.mkdir(parents=True, exist_ok=True)
    path = dir_ / f"{name}.yaml"
    path.write_text(yaml.safe_dump({"actions": actions}), encoding="utf-8")
    return path


def test_load_recommendations_parses_yaml(tmp_path: Path) -> None:
    _write_reco(
        tmp_path,
        "S20",
        [
            {
                "platform": "google",
                "action": "pause",
                "target": "kw:audit-pentest",
                "eur_delta_week": -120.0,
                "rationale": "CPA 3x trop élevé sur 4 semaines",
            },
            {
                "platform": "linkedin",
                "action": "scale",
                "target": "campaign:icp-ciso",
                "eur_delta_week": 80.0,
                "rationale": "CTR 4.2% vs 1.1% médiane",
            },
        ],
    )
    with patch("argos_ops.agents.ad_bot_live.RECOMMENDATIONS_DIR", tmp_path):
        actions = load_recommendations()
    assert len(actions) == 2
    assert {a.platform for a in actions} == {"google", "linkedin"}
    assert actions[0].eur_delta_week == -120.0


def test_load_recommendations_skips_invalid_entries(tmp_path: Path) -> None:
    _write_reco(tmp_path, "mixed", [{"platform": "meta", "action": "pause"}, "not-a-dict"])
    with patch("argos_ops.agents.ad_bot_live.RECOMMENDATIONS_DIR", tmp_path):
        actions = load_recommendations()
    assert len(actions) == 1


def test_build_ad_embed_yellow_in_shadow() -> None:
    stats = AdRunStats(recos_read=3, actions_shadow=3, eur_committed_week=50.0)
    embed = build_ad_embed(stats, live_mode=False, budget=0)
    assert embed.color == YELLOW


def test_build_ad_embed_green_in_live_no_blocks() -> None:
    stats = AdRunStats(recos_read=2, actions_applied=2, eur_committed_week=-40.0)
    embed = build_ad_embed(stats, live_mode=True, budget=20)
    assert embed.color == GREEN


def test_build_ad_embed_orange_when_blocked() -> None:
    stats = AdRunStats(recos_read=2, actions_applied=1, actions_blocked=1)
    embed = build_ad_embed(stats, live_mode=True, budget=10)
    assert embed.color == ORANGE


@pytest.mark.asyncio
async def test_adbot_shadow_does_not_apply_but_archives(tmp_path: Path) -> None:
    from argos_ops.agents.ad_bot_live import AdBotLive

    recos_dir = tmp_path / "recos"
    applied_dir = tmp_path / "applied"
    _write_reco(
        recos_dir,
        "S20",
        [
            {
                "platform": "google",
                "action": "pause",
                "target": "kw:audit",
                "eur_delta_week": -50.0,
                "rationale": "perf basse",
            }
        ],
    )

    fake_settings = type(
        "S",
        (),
        {
            "ads_live_mode": False,
            "ads_daily_budget_eur": 0,
            "discord_webhook_ops_logs": None,
            "discord_webhook_alerts": None,
        },
    )()

    with (
        patch("argos_ops.agents.ad_bot_live.RECOMMENDATIONS_DIR", recos_dir),
        patch("argos_ops.agents.ad_bot_live.APPLIED_DIR", applied_dir),
        patch("argos_ops.agents.ad_bot_live.get_settings", return_value=fake_settings),
    ):
        result = await AdBotLive().run()

    assert result.status == "success"
    assert "shadow=1" in (result.output_summary or "")
    assert "applied=0" in (result.output_summary or "")
    assert any(applied_dir.glob("*.yaml"))


def test_adaction_dataclass_basic() -> None:
    act = AdAction(platform="meta", action="scale", target="ad:42", eur_delta_week=15.0, rationale="ok")
    assert act.platform == "meta"
    assert act.eur_delta_week == 15.0
