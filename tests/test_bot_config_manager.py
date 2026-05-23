"""Tests unitaires de :mod:`argos_ops.agents.bot_config_manager` (P22.C).

Couvre :
- ``load_baseline`` : fichier absent → ``{}``
- ``collect_drifts`` : détection de drifts sur enabled/intensity/daily_limit
- ``collect_drifts`` : missing_in_db / missing_in_baseline
- ``collect_drifts`` : couleur RED si drift ``enabled``, YELLOW sinon
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from argos_ops.agents import bot_config_manager
from argos_ops.agents.bot_config_manager import collect_drifts, load_baseline
from argos_ops.crm.models import AgentConfig
from argos_ops.notifications.discord import GREEN, RED, YELLOW


def _config(
    name: str, *, enabled: bool = True, intensity: int = 5, daily_limit: int | None = 100
) -> AgentConfig:
    return AgentConfig(
        agent_name=name,
        enabled=enabled,
        intensity_level=intensity,
        daily_limit=daily_limit,
    )


# =============================================================================
# load_baseline
# =============================================================================
def test_load_baseline_missing_file_returns_empty(tmp_path: Path) -> None:
    assert load_baseline(tmp_path / "nope.yaml") == {}


def test_load_baseline_empty_file_returns_empty(tmp_path: Path) -> None:
    path = tmp_path / "baseline.yaml"
    path.write_text("", encoding="utf-8")
    assert load_baseline(path) == {}


def test_load_baseline_parses_agents_section(tmp_path: Path) -> None:
    path = tmp_path / "baseline.yaml"
    path.write_text(
        "agents:\n"
        "  EmailBot:\n"
        "    enabled: true\n"
        "    intensity_level: 7\n",
        encoding="utf-8",
    )
    baseline = load_baseline(path)
    assert baseline["EmailBot"]["intensity_level"] == 7


# =============================================================================
# collect_drifts
# =============================================================================
@pytest.mark.asyncio
async def test_collect_drifts_detects_intensity_drift() -> None:
    session = MagicMock()
    baseline: dict[str, dict[str, Any]] = {"EmailBot": {"intensity_level": 5}}
    db = {"EmailBot": _config("EmailBot", intensity=8)}
    with patch.object(bot_config_manager, "_load_db_configs", new=AsyncMock(return_value=db)):
        report = await collect_drifts(session, baseline=baseline)
    assert len(report.drifts) == 1
    assert report.drifts[0].field == "intensity_level"
    assert report.alert_color == YELLOW


@pytest.mark.asyncio
async def test_collect_drifts_detects_enabled_drift_as_red() -> None:
    session = MagicMock()
    baseline: dict[str, dict[str, Any]] = {"EmailBot": {"enabled": True}}
    db = {"EmailBot": _config("EmailBot", enabled=False)}
    with patch.object(bot_config_manager, "_load_db_configs", new=AsyncMock(return_value=db)):
        report = await collect_drifts(session, baseline=baseline)
    assert report.alert_color == RED
    assert report.drifts[0].field == "enabled"


@pytest.mark.asyncio
async def test_collect_drifts_detects_daily_limit_drift() -> None:
    session = MagicMock()
    baseline: dict[str, dict[str, Any]] = {"EmailBot": {"daily_limit": 100}}
    db = {"EmailBot": _config("EmailBot", daily_limit=50)}
    with patch.object(bot_config_manager, "_load_db_configs", new=AsyncMock(return_value=db)):
        report = await collect_drifts(session, baseline=baseline)
    assert len(report.drifts) == 1
    assert report.drifts[0].field == "daily_limit"
    assert report.alert_color == YELLOW


@pytest.mark.asyncio
async def test_collect_drifts_flags_missing_in_db() -> None:
    session = MagicMock()
    baseline: dict[str, dict[str, Any]] = {"GhostBot": {"enabled": True}}
    with patch.object(bot_config_manager, "_load_db_configs", new=AsyncMock(return_value={})):
        report = await collect_drifts(session, baseline=baseline)
    assert "GhostBot" in report.missing_in_db
    assert report.should_alert is True


@pytest.mark.asyncio
async def test_collect_drifts_flags_missing_in_baseline() -> None:
    session = MagicMock()
    db = {"NewBot": _config("NewBot")}
    with patch.object(bot_config_manager, "_load_db_configs", new=AsyncMock(return_value=db)):
        report = await collect_drifts(session, baseline={})
    assert "NewBot" in report.missing_in_baseline


@pytest.mark.asyncio
async def test_collect_drifts_green_when_no_diff() -> None:
    session = MagicMock()
    baseline: dict[str, dict[str, Any]] = {
        "EmailBot": {"enabled": True, "intensity_level": 5, "daily_limit": 100}
    }
    db = {"EmailBot": _config("EmailBot", enabled=True, intensity=5, daily_limit=100)}
    with patch.object(bot_config_manager, "_load_db_configs", new=AsyncMock(return_value=db)):
        report = await collect_drifts(session, baseline=baseline)
    assert report.should_alert is False
    assert report.alert_color == GREEN
