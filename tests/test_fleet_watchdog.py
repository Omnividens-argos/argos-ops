"""Tests de :mod:`argos_ops.agents.fleet_watchdog` (Axe 3.2, fusion D-031).

Couvre la logique d'agrégation ajoutée par la fusion (la logique pure des
4 sous-sections reste testée dans ``test_bot_health`` / ``test_bot_perf_analyzer``
/ ``test_error_triage`` / ``test_log_anomaly``) :
- ``aggregate_report`` : OR des alertes + couleur « pire gagne » + summary
- ``build_fleet_embed`` : seules les sections en alerte sont dépliées + cap 25
- ``FleetWatchdog.run`` : chemin silence (tout vert → aucun push Discord)
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from argos_ops.agents import _watcher_base, fleet_watchdog
from argos_ops.agents._watchdog import anomaly, errors, health, perf
from argos_ops.agents.fleet_watchdog import (
    FleetWatchdog,
    _build_io,
    _worst_color,
    aggregate_report,
    build_fleet_embed,
)
from argos_ops.crm.models import Breaker
from argos_ops.notifications.discord import GREEN, RED, YELLOW


# =============================================================================
# Helpers : sous-rapports minimaux par couleur
# =============================================================================
def _health(color: int, *, alert: bool, summary: str = "h") -> health.BotHealthReport:
    return health.BotHealthReport(
        snapshots=[], tripped_breakers=[], should_alert=alert, alert_color=color, summary=summary
    )


def _perf(color: int, *, alert: bool, summary: str = "p") -> perf.PerfReport:
    return perf.PerfReport(snapshots=[], should_alert=alert, alert_color=color, summary=summary)


def _triage(color: int, *, alert: bool, summary: str = "t") -> errors.TriageReport:
    return errors.TriageReport(
        clusters=[], total_errors=0, should_alert=alert, alert_color=color, summary=summary
    )


def _anomaly(color: int, *, alert: bool, summary: str = "a") -> anomaly.AnomalyReport:
    status = "normal" if color == GREEN else ("spike_warn" if color == YELLOW else "spike_critical")
    return anomaly.AnomalyReport(
        current_count=0,
        baseline_hourly=0.0,
        ratio=0.0,
        top_agents=[],
        status=status,  # type: ignore[arg-type]
        should_alert=alert,
        alert_color=color,
        summary=summary,
    )


# =============================================================================
# _worst_color
# =============================================================================
def test_worst_color_picks_red_over_yellow_over_green() -> None:
    assert _worst_color(GREEN, YELLOW, RED, GREEN) == RED
    assert _worst_color(GREEN, YELLOW, GREEN) == YELLOW
    assert _worst_color(GREEN, GREEN, GREEN, GREEN) == GREEN


# =============================================================================
# aggregate_report
# =============================================================================
def test_aggregate_silent_when_all_green() -> None:
    report = aggregate_report(
        _health(GREEN, alert=False),
        _perf(GREEN, alert=False),
        _triage(GREEN, alert=False),
        _anomaly(GREEN, alert=False),
    )
    assert report.should_alert is False
    assert report.alert_color == GREEN
    assert "santé [GREEN]" in report.summary
    assert "anomalie [GREEN]" in report.summary


def test_aggregate_yellow_when_one_section_warns() -> None:
    report = aggregate_report(
        _health(GREEN, alert=False),
        _perf(YELLOW, alert=True),
        _triage(GREEN, alert=False),
        _anomaly(GREEN, alert=False),
    )
    assert report.should_alert is True
    assert report.alert_color == YELLOW
    assert "perf [YELLOW]" in report.summary


def test_aggregate_red_wins_over_yellow() -> None:
    report = aggregate_report(
        _health(YELLOW, alert=True),
        _perf(GREEN, alert=False),
        _triage(RED, alert=True),
        _anomaly(GREEN, alert=False),
    )
    assert report.should_alert is True
    assert report.alert_color == RED  # le plus sévère gagne


# =============================================================================
# build_fleet_embed
# =============================================================================
def test_embed_only_expands_alerting_sections() -> None:
    stats = perf.PerfStats(p50_seconds=1.0, p95_seconds=2.0, error_rate=0.0, sample_size=10)
    warn_snap = perf.PerfSnapshot(
        agent_name="EmailBot",
        current=stats,
        baseline=stats,
        p95_ratio=1.6,
        error_ratio=None,
        status="warn",
        reason="P95 x1.60",
    )
    report = aggregate_report(
        _health(GREEN, alert=False),
        perf.build_report([warn_snap]),  # yellow
        _triage(GREEN, alert=False),
        _anomaly(GREEN, alert=False),
    )
    embed = build_fleet_embed(report)
    names = [f.name for f in embed.fields]
    # En-tête de la section perf présent, sections vertes absentes.
    assert any("Perf" in n for n in names)
    assert not any("Santé" in n for n in names)
    assert not any("Anomalie" in n for n in names)
    # Le détail par agent de la section en alerte est bien déplié.
    assert any("EmailBot" in f.name for f in embed.fields)
    assert embed.color == YELLOW
    assert "YELLOW" in embed.title


def test_embed_title_color_matches_worst_section() -> None:
    cluster = errors.ErrorCluster(
        signature="OOM", count=15, affected_agents=["FinanceBot"], sample_message="OOM: killed"
    )
    report = aggregate_report(
        _health(GREEN, alert=False),
        _perf(GREEN, alert=False),
        errors.build_report([cluster], 15),  # red (>=10)
        _anomaly(GREEN, alert=False),
    )
    embed = build_fleet_embed(report)
    assert embed.color == RED
    assert "RED" in embed.title


def test_embed_caps_fields_at_25() -> None:
    snaps = [
        health.BotHealthSnapshot(
            agent_name=f"Bot{i}",
            last_run_at=None,
            last_run_status=None,
            avg_duration_seconds_7d=None,
            age_hours=None,
            threshold_hours=24.0,
            recent_errors_24h=0,
            status="stale",
        )
        for i in range(30)
    ]
    report = aggregate_report(
        health.build_report(snaps, []),  # yellow, 30 fields
        _perf(GREEN, alert=False),
        _triage(GREEN, alert=False),
        _anomaly(GREEN, alert=False),
    )
    embed = build_fleet_embed(report)
    assert len(embed.fields) == 25
    assert "tronqué" in embed.fields[-1].value


# =============================================================================
# FleetWatchdog.run — chemin silence (aucun Discord)
# =============================================================================
@pytest.mark.asyncio
async def test_run_silence_when_all_green() -> None:
    @asynccontextmanager
    async def _fake_scope() -> Any:
        yield object()

    with (
        patch.object(fleet_watchdog, "session_scope", _fake_scope),
        patch.object(fleet_watchdog, "list_tripped_breakers", new=AsyncMock(return_value=[])),
        patch.object(health, "collect_snapshots", new=AsyncMock(return_value=[])),
        patch.object(perf, "collect_snapshots", new=AsyncMock(return_value=[])),
        patch.object(errors, "collect_clusters", new=AsyncMock(return_value=([], 0))),
        patch.object(
            anomaly,
            "collect_anomaly",
            new=AsyncMock(return_value=anomaly.build_report(0, 0.0, [])),
        ),
    ):
        result = await FleetWatchdog().run()

    assert result.status == "success"
    assert result.output_summary is not None
    assert result.output_summary.startswith("silence (vert)")


# =============================================================================
# build_fleet_embed — scénarios multi-sections / breaker-only
# =============================================================================
def _warn_perf_report() -> perf.PerfReport:
    stats = perf.PerfStats(p50_seconds=1.0, p95_seconds=2.0, error_rate=0.0, sample_size=10)
    snap = perf.PerfSnapshot(
        agent_name="EmailBot",
        current=stats,
        baseline=stats,
        p95_ratio=1.6,
        error_ratio=None,
        status="warn",
        reason="P95 x1.60",
    )
    return perf.build_report([snap])


def _red_triage_report() -> errors.TriageReport:
    cluster = errors.ErrorCluster(
        signature="OOM", count=15, affected_agents=["FinanceBot"], sample_message="OOM: killed"
    )
    return errors.build_report([cluster], 15)


def test_embed_expands_multiple_alerting_sections() -> None:
    """2 sections alertent (perf jaune + triage rouge) → les 2 en-têtes
    sont dépliés, les 2 sections vertes masquées, couleur = pire (RED)."""
    report = aggregate_report(
        _health(GREEN, alert=False),
        _warn_perf_report(),
        _red_triage_report(),
        _anomaly(GREEN, alert=False),
    )
    embed = build_fleet_embed(report)
    names = [f.name for f in embed.fields]
    assert any("Perf" in n for n in names)
    assert any("Triage" in n for n in names)
    assert not any("Santé" in n for n in names)
    assert not any("Anomalie" in n for n in names)
    # détails des 2 sections présents
    assert any("EmailBot" in f.name for f in embed.fields)
    assert any("OOM" in f.name for f in embed.fields)
    assert embed.color == RED  # le plus sévère gagne


def test_embed_expands_health_section_for_breaker_only() -> None:
    """Santé RED via un breaker tripped alors qu'aucun agent n'est snapshoté
    → la section santé est dépliée avec son field 'Breakers tripped'."""
    breaker = Breaker(name="mrr_drop_critical", tripped=True, tripped_at=None, reason="MRR -12%")
    health_report = health.build_report([], [breaker])
    assert health_report.should_alert is True
    assert health_report.alert_color == RED
    report = aggregate_report(
        health_report,
        _perf(GREEN, alert=False),
        _triage(GREEN, alert=False),
        _anomaly(GREEN, alert=False),
    )
    embed = build_fleet_embed(report)
    assert embed.color == RED
    assert any("Santé" in f.name for f in embed.fields)
    assert any(f.name == "Breakers tripped" for f in embed.fields)
    assert any("mrr_drop_critical" in f.value for f in embed.fields)


# =============================================================================
# _build_io — union IN/OUT des 4 sections (valeur cockpit)
# =============================================================================
def test_build_io_unions_the_four_sections() -> None:
    stale = health.BotHealthSnapshot(
        agent_name="EmailBot",
        last_run_at=None,
        last_run_status=None,
        avg_duration_seconds_7d=None,
        age_hours=None,
        threshold_hours=14.5,
        recent_errors_24h=0,
        status="stale",
    )
    errored = health.BotHealthSnapshot(
        agent_name="FinanceBot",
        last_run_at=None,
        last_run_status="failed",
        avg_duration_seconds_7d=4.2,
        age_hours=3.0,
        threshold_hours=26.0,
        recent_errors_24h=2,
        status="error",
    )
    breaker = Breaker(name="stripe_api_error_burst", tripped=True, tripped_at=None, reason="429")
    health_report = health.build_report([stale, errored], [breaker])

    stats = perf.PerfStats(p50_seconds=1.0, p95_seconds=2.0, error_rate=0.0, sample_size=10)
    reg = perf.PerfSnapshot("DigestBuilder", stats, stats, 2.5, None, "regression", "P95 x2.50")
    warn = perf.PerfSnapshot("EmailBot", stats, stats, 1.6, None, "warn", "P95 x1.60")
    perf_report = perf.build_report([reg, warn])

    cluster = errors.ErrorCluster(
        signature="ConnectionError", count=4, affected_agents=["EmailBot"], sample_message="refused"
    )
    triage_report = errors.build_report([cluster], 4)

    anomaly_report = anomaly.build_report(60, 10.0, [("FinanceBot", 40)])

    inputs, outputs = _build_io(health_report, perf_report, triage_report, anomaly_report)

    assert len(inputs) == 4
    assert inputs[0].count == 2  # agents surveillés
    assert inputs[1].count == 1  # breakers
    assert inputs[2].count == 4  # erreurs runtime 24h (total_errors)
    assert inputs[3].count == 60  # erreurs dernière heure

    stale_out = next(o for o in outputs if "stale" in o.label.lower())
    assert stale_out.count == 1 and stale_out.detail is not None and "EmailBot" in stale_out.detail
    err_out = next(o for o in outputs if o.label == "Agents en erreur")
    assert err_out.count == 1 and err_out.detail is not None and "FinanceBot" in err_out.detail
    reg_out = next(o for o in outputs if "Régressions" in o.label)
    assert reg_out.count == 1
    warn_out = next(o for o in outputs if "Dérives" in o.label)
    assert warn_out.count == 1
    cluster_out = next(o for o in outputs if "Clusters" in o.label)
    assert cluster_out.count == 1
    spike_out = next(o for o in outputs if "Pic" in o.label)
    assert spike_out.count == 60 and "spike_critical" in spike_out.label


# =============================================================================
# FleetWatchdog.run — chemin alerte (push tenté, webhook absent → pas de HTTP)
# =============================================================================
@pytest.mark.asyncio
async def test_run_alert_path_when_section_red() -> None:
    """Un breaker tripped rend la section santé rouge → should_alert ; sans
    webhook configuré, emit retourne 'alerte non envoyée' (aucun appel HTTP)."""

    @asynccontextmanager
    async def _fake_scope() -> Any:
        yield object()

    breaker = Breaker(name="mrr_drop_critical", tripped=True, tripped_at=None, reason="boom")
    with (
        patch.object(fleet_watchdog, "session_scope", _fake_scope),
        patch.object(
            fleet_watchdog, "list_tripped_breakers", new=AsyncMock(return_value=[breaker])
        ),
        patch.object(health, "collect_snapshots", new=AsyncMock(return_value=[])),
        patch.object(perf, "collect_snapshots", new=AsyncMock(return_value=[])),
        patch.object(errors, "collect_clusters", new=AsyncMock(return_value=([], 0))),
        patch.object(
            anomaly, "collect_anomaly", new=AsyncMock(return_value=anomaly.build_report(0, 0.0, []))
        ),
        patch.object(
            _watcher_base,
            "get_settings",
            return_value=SimpleNamespace(discord_webhook_ops_logs=None),
        ),
    ):
        result = await FleetWatchdog().run()

    assert result.status == "success"
    assert result.output_summary is not None
    assert result.output_summary.startswith("alerte non envoyée")
