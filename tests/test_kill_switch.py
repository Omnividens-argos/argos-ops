"""Tests unitaires de :mod:`argos_ops.agents.kill_switch` (P22.C).

Couvre :
- ``_breaker_age_hours`` : None safe + naive datetime
- ``collect_candidates`` : filtre breakers < MIN_STALE_HOURS + dédup
- ``build_report`` : suppression breakers déjà alertés + couleur
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from argos_ops.agents import kill_switch
from argos_ops.agents.kill_switch import (
    StaleBreaker,
    _breaker_age_hours,
    build_report,
    collect_candidates,
)
from argos_ops.crm.models import Breaker
from argos_ops.notifications.discord import GREEN, RED, YELLOW


def _breaker(name: str, hours_ago: float | None, *, naive: bool = False) -> Breaker:
    if hours_ago is None:
        tripped_at = None
    else:
        tripped_at = datetime.now(UTC) - timedelta(hours=hours_ago)
        if naive:
            tripped_at = tripped_at.replace(tzinfo=None)
    return Breaker(name=name, tripped=True, tripped_at=tripped_at, reason="test")


# =============================================================================
# _breaker_age_hours
# =============================================================================
def test_breaker_age_hours_none_when_tripped_at_missing() -> None:
    breaker = _breaker("foo", hours_ago=None)
    assert _breaker_age_hours(breaker, now=datetime.now(UTC)) is None


def test_breaker_age_hours_handles_naive_datetime() -> None:
    """Si ``tripped_at`` est naive (legacy DB), on suppose UTC."""
    breaker = _breaker("foo", hours_ago=3.0, naive=True)
    age = _breaker_age_hours(breaker, now=datetime.now(UTC))
    assert age is not None
    assert 2.5 < age < 3.5


def test_breaker_age_hours_computes_aware() -> None:
    breaker = _breaker("foo", hours_ago=10.0)
    age = _breaker_age_hours(breaker, now=datetime.now(UTC))
    assert age is not None
    assert 9.5 < age < 10.5


# =============================================================================
# collect_candidates
# =============================================================================
@pytest.mark.asyncio
async def test_collect_candidates_filters_below_min_stale() -> None:
    """Breaker tripped depuis 1h (< MIN_STALE_HOURS=4h) → ignoré."""
    session = MagicMock()
    breakers = [_breaker("fresh", hours_ago=1.0), _breaker("stale", hours_ago=10.0)]
    with (
        patch.object(
            kill_switch, "list_tripped_breakers", new=AsyncMock(return_value=breakers)
        ),
        patch.object(
            kill_switch, "_recent_alerted_breakers", new=AsyncMock(return_value=set())
        ),
    ):
        candidates = await collect_candidates(session)
    assert len(candidates) == 1
    assert candidates[0].name == "stale"


@pytest.mark.asyncio
async def test_collect_candidates_marks_already_alerted() -> None:
    """Breaker stale ET déjà alerté → flag ``already_alerted_recently``."""
    session = MagicMock()
    breakers = [_breaker("old", hours_ago=12.0)]
    with (
        patch.object(
            kill_switch, "list_tripped_breakers", new=AsyncMock(return_value=breakers)
        ),
        patch.object(
            kill_switch, "_recent_alerted_breakers", new=AsyncMock(return_value={"old"})
        ),
    ):
        candidates = await collect_candidates(session)
    assert len(candidates) == 1
    assert candidates[0].already_alerted_recently is True


# =============================================================================
# build_report
# =============================================================================
def _stale(name: str, age: float, *, already_alerted: bool = False) -> StaleBreaker:
    return StaleBreaker(
        name=name,
        age_hours=age,
        reason="test",
        already_alerted_recently=already_alerted,
    )


def test_build_report_suppresses_already_alerted() -> None:
    report = build_report(
        [_stale("a", age=10.0, already_alerted=True), _stale("b", age=8.0)]
    )
    assert len(report.to_alert) == 1
    assert report.to_alert[0].name == "b"
    assert "1 suppressed" in report.summary


def test_build_report_green_when_only_suppressed() -> None:
    """Tous les candidats sont déjà alertés → silence."""
    report = build_report([_stale("a", age=10.0, already_alerted=True)])
    assert report.should_alert is False
    assert report.alert_color == GREEN


def test_build_report_yellow_when_stale_under_critical() -> None:
    report = build_report([_stale("a", age=10.0)])
    assert report.should_alert is True
    assert report.alert_color == YELLOW


def test_build_report_red_when_above_critical() -> None:
    report = build_report([_stale("a", age=30.0)])
    assert report.alert_color == RED
    assert report.should_alert is True
