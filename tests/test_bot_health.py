"""Tests unitaires de :mod:`argos_ops.agents.bot_health` (P22.B).

Couvrent la logique déterministe :
- ``collect_snapshots`` : classification ok / stale / error par agent
- ``build_report`` : politique d'alerte (silence si tout vert, jaune si
  stale, rouge si error ou breaker)
- ``build_health_embed`` : structure de l'embed Discord

Les ops DB sont mockées — pas de Postgres nécessaire.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from argos_ops.agents import bot_health
from argos_ops.agents.bot_health import (
    BotHealthSnapshot,
    build_health_embed,
    build_report,
    collect_snapshots,
)
from argos_ops.crm.models import AgentRun, Breaker
from argos_ops.notifications.discord import GREEN, RED, YELLOW


def _make_run(agent: str, hours_ago: float, status: str = "success") -> AgentRun:
    started_at = datetime.now(UTC) - timedelta(hours=hours_ago)
    return AgentRun(
        agent_name=agent,
        command=None,
        status=status,
        started_at=started_at,
        ended_at=started_at + timedelta(seconds=2.5),
    )


def _make_breaker(name: str, hours_ago: float = 1.0, reason: str = "test") -> Breaker:
    return Breaker(
        name=name,
        tripped=True,
        tripped_at=datetime.now(UTC) - timedelta(hours=hours_ago),
        reason=reason,
    )


# =============================================================================
# collect_snapshots
# =============================================================================
@pytest.mark.asyncio
async def test_collect_snapshots_ok_when_recent_and_no_errors() -> None:
    session = MagicMock()
    with (
        patch.object(
            bot_health,
            "get_last_run_per_agent",
            new=AsyncMock(
                return_value={
                    "DigestBuilder": _make_run("DigestBuilder", hours_ago=2.0),
                }
            ),
        ),
        patch.object(bot_health, "_avg_duration_seconds", new=AsyncMock(return_value=2.5)),
        patch.object(bot_health, "_count_recent_errors", new=AsyncMock(return_value=0)),
    ):
        snapshots = await collect_snapshots(
            session,
            agent_names=["DigestBuilder"],
            max_age_hours={"DigestBuilder": 26.0},
        )
    assert len(snapshots) == 1
    assert snapshots[0].status == "ok"
    assert snapshots[0].last_run_status == "success"
    assert snapshots[0].recent_errors_24h == 0
    assert snapshots[0].avg_duration_seconds_7d == 2.5


@pytest.mark.asyncio
async def test_collect_snapshots_stale_when_no_run_ever() -> None:
    """Un agent attendu mais jamais run en DB → stale (cas critique)."""
    session = MagicMock()
    with (
        patch.object(bot_health, "get_last_run_per_agent", new=AsyncMock(return_value={})),
        patch.object(bot_health, "_avg_duration_seconds", new=AsyncMock(return_value=None)),
        patch.object(bot_health, "_count_recent_errors", new=AsyncMock(return_value=0)),
    ):
        snapshots = await collect_snapshots(
            session,
            agent_names=["EmailBot"],
            max_age_hours={"EmailBot": 14.5},
        )
    assert snapshots[0].status == "stale"
    assert snapshots[0].last_run_at is None
    assert snapshots[0].age_hours is None


@pytest.mark.asyncio
async def test_collect_snapshots_stale_when_past_threshold() -> None:
    """EmailBot threshold=14.5h ; dernier run il y a 20h → stale."""
    session = MagicMock()
    with (
        patch.object(
            bot_health,
            "get_last_run_per_agent",
            new=AsyncMock(return_value={"EmailBot": _make_run("EmailBot", hours_ago=20.0)}),
        ),
        patch.object(bot_health, "_avg_duration_seconds", new=AsyncMock(return_value=1.0)),
        patch.object(bot_health, "_count_recent_errors", new=AsyncMock(return_value=0)),
    ):
        snapshots = await collect_snapshots(
            session,
            agent_names=["EmailBot"],
            max_age_hours={"EmailBot": 14.5},
        )
    assert snapshots[0].status == "stale"
    assert snapshots[0].age_hours is not None
    assert snapshots[0].age_hours > 14.5


@pytest.mark.asyncio
async def test_collect_snapshots_error_wins_over_stale() -> None:
    """Un run frais OK mais aussi 1 erreur 24h → status=error (priorité)."""
    session = MagicMock()
    with (
        patch.object(
            bot_health,
            "get_last_run_per_agent",
            new=AsyncMock(return_value={"FinanceBot": _make_run("FinanceBot", hours_ago=3.0)}),
        ),
        patch.object(bot_health, "_avg_duration_seconds", new=AsyncMock(return_value=4.2)),
        patch.object(bot_health, "_count_recent_errors", new=AsyncMock(return_value=2)),
    ):
        snapshots = await collect_snapshots(
            session,
            agent_names=["FinanceBot"],
            max_age_hours={"FinanceBot": 26.0},
        )
    assert snapshots[0].status == "error"
    assert snapshots[0].recent_errors_24h == 2


@pytest.mark.asyncio
async def test_collect_snapshots_handles_naive_started_at() -> None:
    """Si ``started_at`` arrive sans tzinfo (cas legacy), on suppose UTC
    plutôt que de crasher avec un TypeError sur la soustraction."""
    naive_dt = (datetime.now(UTC) - timedelta(hours=3.0)).replace(tzinfo=None)
    run = AgentRun(
        agent_name="DigestBuilder",
        command=None,
        status="success",
        started_at=naive_dt,
        ended_at=naive_dt + timedelta(seconds=2.0),
    )
    session = MagicMock()
    with (
        patch.object(
            bot_health,
            "get_last_run_per_agent",
            new=AsyncMock(return_value={"DigestBuilder": run}),
        ),
        patch.object(bot_health, "_avg_duration_seconds", new=AsyncMock(return_value=2.0)),
        patch.object(bot_health, "_count_recent_errors", new=AsyncMock(return_value=0)),
    ):
        snapshots = await collect_snapshots(
            session,
            agent_names=["DigestBuilder"],
            max_age_hours={"DigestBuilder": 26.0},
        )
    assert snapshots[0].age_hours is not None
    assert snapshots[0].status == "ok"


# =============================================================================
# build_report — politique d'alerte
# =============================================================================
def _snap(name: str, status: str, **kwargs: object) -> BotHealthSnapshot:
    defaults: dict[str, object] = {
        "agent_name": name,
        "last_run_at": None,
        "last_run_status": "success",
        "avg_duration_seconds_7d": 1.0,
        "age_hours": 1.0,
        "threshold_hours": 24.0,
        "recent_errors_24h": 0,
        "status": status,
    }
    defaults.update(kwargs)
    return BotHealthSnapshot(**defaults)  # type: ignore[arg-type]


def test_build_report_green_silence_when_all_ok() -> None:
    report = build_report(
        [_snap("DigestBuilder", "ok"), _snap("EmailBot", "ok")],
        tripped=[],
    )
    assert report.should_alert is False
    assert report.alert_color == GREEN
    assert "2 ok" in report.summary


def test_build_report_yellow_when_only_stale() -> None:
    report = build_report(
        [_snap("DigestBuilder", "ok"), _snap("EmailBot", "stale")],
        tripped=[],
    )
    assert report.should_alert is True
    assert report.alert_color == YELLOW


def test_build_report_red_when_error_present() -> None:
    report = build_report(
        [
            _snap("DigestBuilder", "ok"),
            _snap("EmailBot", "stale"),
            _snap("FinanceBot", "error", recent_errors_24h=3),
        ],
        tripped=[],
    )
    assert report.should_alert is True
    assert report.alert_color == RED
    assert "1 error" in report.summary


def test_build_report_red_when_breaker_tripped_even_if_all_agents_ok() -> None:
    report = build_report(
        [_snap("DigestBuilder", "ok")],
        tripped=[_make_breaker("mrr_drop_critical")],
    )
    assert report.should_alert is True
    assert report.alert_color == RED
    assert "1 breaker(s) tripped" in report.summary


# =============================================================================
# build_health_embed — structure de sortie
# =============================================================================
def test_build_health_embed_includes_one_field_per_agent() -> None:
    report = build_report(
        [_snap("DigestBuilder", "ok"), _snap("EmailBot", "stale")],
        tripped=[],
    )
    embed = build_health_embed(report)
    assert len(embed.fields) == 2
    assert any("DigestBuilder" in f.name for f in embed.fields)
    assert any("EmailBot" in f.name for f in embed.fields)


def test_build_health_embed_appends_breakers_field_when_present() -> None:
    report = build_report(
        [_snap("DigestBuilder", "ok")],
        tripped=[_make_breaker("mrr_drop_critical", reason="MRR -12%")],
    )
    embed = build_health_embed(report)
    assert any(f.name == "Breakers tripped" for f in embed.fields)
    breaker_field = next(f for f in embed.fields if f.name == "Breakers tripped")
    assert "mrr_drop_critical" in breaker_field.value
    assert "MRR -12%" in breaker_field.value


def test_build_health_embed_color_matches_report() -> None:
    report = build_report(
        [_snap("DigestBuilder", "error", recent_errors_24h=1)],
        tripped=[],
    )
    embed = build_health_embed(report)
    assert embed.color == RED
    assert "RED" in embed.title
