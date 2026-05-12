"""Tests unitaires du module ``argos_ops.breakers`` (P15).

Mockent ``session_scope`` et les wrappers ``repository.*`` — pas de DB
nécessaire pour ces tests. La logique métier des trip auto (FinanceBot
``mrr_drop_critical`` etc.) est testée en intégration dans les tests
agents respectifs.
"""

from __future__ import annotations

import dataclasses
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import SecretStr

from argos_ops import breakers
from argos_ops.breakers import BreakerStatus
from argos_ops.crm.models import Breaker

_WEBHOOK = SecretStr("https://discord.test/webhook")


# =============================================================================
# Helpers — fake session_scope qui ne fait rien
# =============================================================================
@asynccontextmanager
async def _fake_session_scope() -> object:  # type: ignore[misc]
    yield MagicMock(name="fake-session")


# =============================================================================
# BreakerStatus dataclass
# =============================================================================
def test_breaker_status_immutable() -> None:
    status = BreakerStatus(name="x", tripped=True)
    with pytest.raises(dataclasses.FrozenInstanceError):
        status.tripped = False  # type: ignore[misc]


def test_breaker_status_defaults() -> None:
    status = BreakerStatus(name="x", tripped=False)
    assert status.tripped_at is None
    assert status.reason is None
    assert status.reset_after is None


# =============================================================================
# trip / reset / is_tripped
# =============================================================================
@pytest.mark.asyncio
async def test_trip_calls_repository_with_reason() -> None:
    fake_trip = AsyncMock()
    with (
        patch.object(breakers, "session_scope", _fake_session_scope),
        patch.object(breakers, "_trip_breaker", fake_trip),
    ):
        await breakers.trip("mrr_drop_critical", "MRR -12 %", reset_after=None)
    fake_trip.assert_awaited_once()
    args, kwargs = fake_trip.call_args
    assert args[1] == "mrr_drop_critical"
    assert args[2] == "MRR -12 %"
    assert kwargs == {"reset_after": None}


@pytest.mark.asyncio
async def test_reset_calls_repository() -> None:
    fake_reset = AsyncMock()
    with (
        patch.object(breakers, "session_scope", _fake_session_scope),
        patch.object(breakers, "_reset_breaker", fake_reset),
    ):
        await breakers.reset("mrr_drop_critical")
    fake_reset.assert_awaited_once()
    assert fake_reset.call_args.args[1] == "mrr_drop_critical"


@pytest.mark.asyncio
async def test_is_tripped_returns_repository_result() -> None:
    fake_is_tripped = AsyncMock(return_value=True)
    with (
        patch.object(breakers, "session_scope", _fake_session_scope),
        patch.object(breakers, "_is_breaker_tripped", fake_is_tripped),
    ):
        assert await breakers.is_tripped("FinanceBot") is True

    fake_is_tripped = AsyncMock(return_value=False)
    with (
        patch.object(breakers, "session_scope", _fake_session_scope),
        patch.object(breakers, "_is_breaker_tripped", fake_is_tripped),
    ):
        assert await breakers.is_tripped("FinanceBot") is False


# =============================================================================
# status / list_tripped
# =============================================================================
@pytest.mark.asyncio
async def test_status_returns_none_when_breaker_absent() -> None:
    with (
        patch.object(breakers, "session_scope", _fake_session_scope),
        patch.object(breakers, "_get_breaker", AsyncMock(return_value=None)),
    ):
        assert await breakers.status("never_tripped") is None


@pytest.mark.asyncio
async def test_status_returns_breaker_status_when_present() -> None:
    now = datetime.now(UTC)
    fake = Breaker(name="mrr_drop_critical", tripped=True, tripped_at=now, reason="MRR -12 %")
    with (
        patch.object(breakers, "session_scope", _fake_session_scope),
        patch.object(breakers, "_get_breaker", AsyncMock(return_value=fake)),
    ):
        result = await breakers.status("mrr_drop_critical")
    assert isinstance(result, BreakerStatus)
    assert result.name == "mrr_drop_critical"
    assert result.tripped is True
    assert result.reason == "MRR -12 %"


@pytest.mark.asyncio
async def test_list_tripped_returns_dataclasses() -> None:
    b1 = Breaker(name="a", tripped=True, reason="r1")
    b2 = Breaker(name="b", tripped=True, reason="r2")
    with (
        patch.object(breakers, "session_scope", _fake_session_scope),
        patch.object(breakers, "_list_tripped_breakers", AsyncMock(return_value=[b1, b2])),
    ):
        result = await breakers.list_tripped()
    assert len(result) == 2
    assert all(isinstance(b, BreakerStatus) for b in result)
    assert {b.name for b in result} == {"a", "b"}


# =============================================================================
# count_recent_failed
# =============================================================================
@pytest.mark.asyncio
async def test_count_recent_failed_passes_args() -> None:
    fake_count = AsyncMock(return_value=4)
    with (
        patch.object(breakers, "session_scope", _fake_session_scope),
        patch.object(breakers, "_count_recent_failed_runs", fake_count),
    ):
        assert await breakers.count_recent_failed("FinanceBot", window_minutes=720) == 4
    fake_count.assert_awaited_once()
    kwargs = fake_count.call_args.kwargs
    assert kwargs["agent_name"] == "FinanceBot"
    assert kwargs["window_minutes"] == 720


# =============================================================================
# trip_with_notification — idempotence + Discord embed
# =============================================================================
@pytest.mark.asyncio
async def test_trip_with_notification_skips_when_already_tripped() -> None:
    fake_send = AsyncMock()
    with (
        patch.object(breakers, "session_scope", _fake_session_scope),
        patch.object(breakers, "_is_breaker_tripped", AsyncMock(return_value=True)),
        patch.object(breakers, "send_embed", fake_send),
        patch.object(breakers, "_trip_breaker", AsyncMock()) as fake_trip,
    ):
        await breakers.trip_with_notification(
            "stripe_api_error_burst", "test", discord_webhook=_WEBHOOK
        )
    fake_send.assert_not_awaited()
    fake_trip.assert_not_awaited()


@pytest.mark.asyncio
async def test_trip_with_notification_sends_embed_when_not_tripped() -> None:
    fake_send = AsyncMock()
    with (
        patch.object(breakers, "session_scope", _fake_session_scope),
        patch.object(breakers, "_is_breaker_tripped", AsyncMock(return_value=False)),
        patch.object(breakers, "_trip_breaker", AsyncMock()) as fake_trip,
        patch.object(breakers, "send_embed", fake_send),
    ):
        await breakers.trip_with_notification(
            "mrr_drop_critical", "MRR -15 %", discord_webhook=_WEBHOOK, severity="critical"
        )
    fake_trip.assert_awaited_once()
    fake_send.assert_awaited_once()
    embed = fake_send.call_args.args[1]
    assert "mrr_drop_critical" in embed.title
    assert embed.color == 0xDC2626  # rouge critical
    assert embed.description == "MRR -15 %"


@pytest.mark.asyncio
async def test_trip_with_notification_warning_color() -> None:
    fake_send = AsyncMock()
    with (
        patch.object(breakers, "session_scope", _fake_session_scope),
        patch.object(breakers, "_is_breaker_tripped", AsyncMock(return_value=False)),
        patch.object(breakers, "_trip_breaker", AsyncMock()),
        patch.object(breakers, "send_embed", fake_send),
    ):
        await breakers.trip_with_notification(
            "x", "y", discord_webhook=_WEBHOOK, severity="warning"
        )
    assert fake_send.call_args.args[1].color == 0xF97316  # orange


@pytest.mark.asyncio
async def test_trip_with_notification_info_color() -> None:
    fake_send = AsyncMock()
    with (
        patch.object(breakers, "session_scope", _fake_session_scope),
        patch.object(breakers, "_is_breaker_tripped", AsyncMock(return_value=False)),
        patch.object(breakers, "_trip_breaker", AsyncMock()),
        patch.object(breakers, "send_embed", fake_send),
    ):
        await breakers.trip_with_notification("x", "y", discord_webhook=_WEBHOOK, severity="info")
    assert fake_send.call_args.args[1].color == 0x3B82F6  # bleu


@pytest.mark.asyncio
async def test_trip_with_notification_no_webhook_still_trips() -> None:
    fake_send = AsyncMock()
    fake_trip = AsyncMock()
    with (
        patch.object(breakers, "session_scope", _fake_session_scope),
        patch.object(breakers, "_is_breaker_tripped", AsyncMock(return_value=False)),
        patch.object(breakers, "_trip_breaker", fake_trip),
        patch.object(breakers, "send_embed", fake_send),
    ):
        await breakers.trip_with_notification("x", "y", discord_webhook=None)
    fake_trip.assert_awaited_once()
    fake_send.assert_not_awaited()


@pytest.mark.asyncio
async def test_trip_with_notification_swallows_discord_error() -> None:
    """Un échec de notif Discord ne doit pas faire planter le trip lui-même."""
    fake_send = AsyncMock(side_effect=RuntimeError("Discord down"))
    fake_trip = AsyncMock()
    with (
        patch.object(breakers, "session_scope", _fake_session_scope),
        patch.object(breakers, "_is_breaker_tripped", AsyncMock(return_value=False)),
        patch.object(breakers, "_trip_breaker", fake_trip),
        patch.object(breakers, "send_embed", fake_send),
    ):
        await breakers.trip_with_notification("x", "y", discord_webhook=_WEBHOOK)
    fake_trip.assert_awaited_once()  # le trip est bien passé


# =============================================================================
# in_minutes
# =============================================================================
def test_in_minutes_returns_future_utc() -> None:
    delta = breakers.in_minutes(60)
    now = datetime.now(UTC)
    assert delta > now
    assert delta - now < timedelta(minutes=61)
    assert delta - now > timedelta(minutes=59)
    assert delta.tzinfo is UTC
