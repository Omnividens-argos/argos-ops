"""Tests unitaires d'``argos_ops.agent_runtime`` (P16.B).

Mockent ``session_scope`` et les wrappers ``repository.*`` pour valider
l'ordre de priorité des checks et le mapping verdict → reason.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from argos_ops import agent_runtime
from argos_ops.agent_runtime import check_runtime_state
from argos_ops.crm.models import AgentConfig


@asynccontextmanager
async def _fake_session_scope() -> object:  # type: ignore[misc]
    yield MagicMock(name="fake-session")


def _config(**overrides: object) -> AgentConfig:
    """Fabrique une AgentConfig avec defaults + overrides."""
    base = {
        "agent_name": "FinanceBot",
        "enabled": True,
        "intensity_level": 5,
        "tier1_threshold": 80,
    }
    base.update(overrides)
    return AgentConfig(**base)  # type: ignore[arg-type]


# =============================================================================
# Priorité 1 — breaker tripped court-circuite tout
# =============================================================================
@pytest.mark.asyncio
async def test_breaker_tripped_wins_over_everything() -> None:
    """Même si disabled+paused+over-limit, breaker prime."""
    with (
        patch.object(agent_runtime, "session_scope", _fake_session_scope),
        patch.object(agent_runtime, "is_breaker_tripped", AsyncMock(return_value=True)),
        # get_agent_config et count_runs_today ne devraient pas être appelés
        patch.object(agent_runtime, "get_agent_config", AsyncMock()) as get_cfg,
        patch.object(agent_runtime, "count_runs_today", AsyncMock()) as count,
    ):
        decision = await check_runtime_state("FinanceBot", breaker_name="FinanceBot")
    assert decision.verdict == "killed_by_breaker"
    assert "FinanceBot" in decision.reason
    get_cfg.assert_not_awaited()
    count.assert_not_awaited()


@pytest.mark.asyncio
async def test_no_breaker_name_skips_breaker_check() -> None:
    """Si l'agent n'a pas configuré breaker_name, on saute le check."""
    fake_is_tripped = AsyncMock(return_value=False)
    with (
        patch.object(agent_runtime, "session_scope", _fake_session_scope),
        patch.object(agent_runtime, "is_breaker_tripped", fake_is_tripped),
        patch.object(agent_runtime, "get_agent_config", AsyncMock(return_value=_config())),
        patch.object(agent_runtime, "count_runs_today", AsyncMock(return_value=0)),
    ):
        decision = await check_runtime_state("FinanceBot", breaker_name=None)
    assert decision.verdict == "allowed"
    fake_is_tripped.assert_not_awaited()


# =============================================================================
# Priorité 2 — disabled
# =============================================================================
@pytest.mark.asyncio
async def test_disabled_skips() -> None:
    with (
        patch.object(agent_runtime, "session_scope", _fake_session_scope),
        patch.object(agent_runtime, "is_breaker_tripped", AsyncMock(return_value=False)),
        patch.object(
            agent_runtime, "get_agent_config", AsyncMock(return_value=_config(enabled=False))
        ),
        patch.object(agent_runtime, "count_runs_today", AsyncMock()) as count,
    ):
        decision = await check_runtime_state("FinanceBot", breaker_name="FinanceBot")
    assert decision.verdict == "skipped_disabled"
    assert "disabled" in decision.reason.lower()
    count.assert_not_awaited()


# =============================================================================
# Priorité 3 — paused_until
# =============================================================================
@pytest.mark.asyncio
async def test_paused_until_future_blocks() -> None:
    future = datetime.now(UTC) + timedelta(hours=1)
    with (
        patch.object(agent_runtime, "session_scope", _fake_session_scope),
        patch.object(agent_runtime, "is_breaker_tripped", AsyncMock(return_value=False)),
        patch.object(
            agent_runtime,
            "get_agent_config",
            AsyncMock(return_value=_config(paused_until=future)),
        ),
        patch.object(agent_runtime, "count_runs_today", AsyncMock()) as count,
    ):
        decision = await check_runtime_state("FinanceBot", breaker_name="FinanceBot")
    assert decision.verdict == "skipped_paused"
    assert "paused" in decision.reason.lower()
    count.assert_not_awaited()


@pytest.mark.asyncio
async def test_paused_until_past_does_not_block() -> None:
    """Une pause expirée ne doit pas bloquer."""
    past = datetime.now(UTC) - timedelta(hours=1)
    with (
        patch.object(agent_runtime, "session_scope", _fake_session_scope),
        patch.object(agent_runtime, "is_breaker_tripped", AsyncMock(return_value=False)),
        patch.object(
            agent_runtime,
            "get_agent_config",
            AsyncMock(return_value=_config(paused_until=past)),
        ),
        patch.object(agent_runtime, "count_runs_today", AsyncMock(return_value=0)),
    ):
        decision = await check_runtime_state("FinanceBot", breaker_name="FinanceBot")
    assert decision.verdict == "allowed"


# =============================================================================
# Priorité 4 — daily_limit
# =============================================================================
@pytest.mark.asyncio
async def test_daily_limit_reached_blocks() -> None:
    with (
        patch.object(agent_runtime, "session_scope", _fake_session_scope),
        patch.object(agent_runtime, "is_breaker_tripped", AsyncMock(return_value=False)),
        patch.object(
            agent_runtime,
            "get_agent_config",
            AsyncMock(return_value=_config(daily_limit=5)),
        ),
        patch.object(agent_runtime, "count_runs_today", AsyncMock(return_value=5)),
    ):
        decision = await check_runtime_state("FinanceBot", breaker_name="FinanceBot")
    assert decision.verdict == "skipped_daily_limit"
    assert "5/5" in decision.reason


@pytest.mark.asyncio
async def test_daily_limit_not_yet_reached_allows() -> None:
    with (
        patch.object(agent_runtime, "session_scope", _fake_session_scope),
        patch.object(agent_runtime, "is_breaker_tripped", AsyncMock(return_value=False)),
        patch.object(
            agent_runtime,
            "get_agent_config",
            AsyncMock(return_value=_config(daily_limit=5)),
        ),
        patch.object(agent_runtime, "count_runs_today", AsyncMock(return_value=2)),
    ):
        decision = await check_runtime_state("FinanceBot", breaker_name="FinanceBot")
    assert decision.verdict == "allowed"


@pytest.mark.asyncio
async def test_daily_limit_none_means_unlimited() -> None:
    """daily_limit=None doit signifier illimité, pas bloquer à count=0."""
    with (
        patch.object(agent_runtime, "session_scope", _fake_session_scope),
        patch.object(agent_runtime, "is_breaker_tripped", AsyncMock(return_value=False)),
        patch.object(
            agent_runtime, "get_agent_config", AsyncMock(return_value=_config(daily_limit=None))
        ),
        patch.object(agent_runtime, "count_runs_today", AsyncMock()) as count,
    ):
        decision = await check_runtime_state("FinanceBot", breaker_name="FinanceBot")
    assert decision.verdict == "allowed"
    # count_runs_today ne doit même pas être appelé si daily_limit=None
    count.assert_not_awaited()


# =============================================================================
# Allowed (chemin nominal)
# =============================================================================
@pytest.mark.asyncio
async def test_allowed_when_all_checks_pass() -> None:
    with (
        patch.object(agent_runtime, "session_scope", _fake_session_scope),
        patch.object(agent_runtime, "is_breaker_tripped", AsyncMock(return_value=False)),
        patch.object(agent_runtime, "get_agent_config", AsyncMock(return_value=_config())),
        patch.object(agent_runtime, "count_runs_today", AsyncMock(return_value=0)),
    ):
        decision = await check_runtime_state("FinanceBot", breaker_name="FinanceBot")
    assert decision.verdict == "allowed"
    assert decision.reason == "ok"
