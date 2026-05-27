"""Tests unitaires du module ``argos_ops.health`` (P19).

Couvrent la logique déterministe (agrégation, calcul d'âge, seuils
yellow/red). Les ops DB sont mockées via ``unittest.mock`` — pas de
Postgres nécessaire pour ces tests.
"""

from __future__ import annotations

import dataclasses
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from argos_ops import health
from argos_ops.crm.models import AgentRun, Breaker
from argos_ops.health import (
    DEFAULT_QUEUED_ALERT_COUNT,
    HealthCheck,
    aggregate_health,
    check_agent_freshness,
    check_kb_seeded,
    check_queued_escalations,
    check_tripped_breakers,
    run_all_checks,
)


# =============================================================================
# HealthCheck dataclass
# =============================================================================
def test_health_check_immutable() -> None:
    check = HealthCheck(name="x", status="green", detail="ok")
    with pytest.raises(dataclasses.FrozenInstanceError):
        check.status = "red"  # type: ignore[misc]


def test_health_check_metric_defaults_to_empty_dict() -> None:
    check = HealthCheck(name="x", status="green", detail="ok")
    assert check.metric == {}


# =============================================================================
# aggregate_health — worst status wins
# =============================================================================
def test_aggregate_empty_returns_green_synthetic() -> None:
    overall = aggregate_health([])
    assert overall.status == "green"
    assert overall.metric["total"] == 0


def test_aggregate_all_green_returns_green() -> None:
    checks = [
        HealthCheck(name="a", status="green", detail="ok"),
        HealthCheck(name="b", status="green", detail="ok"),
    ]
    overall = aggregate_health(checks)
    assert overall.status == "green"
    assert overall.metric == {"green": 2, "yellow": 0, "red": 0, "total": 2}


def test_aggregate_one_yellow_returns_yellow() -> None:
    checks = [
        HealthCheck(name="a", status="green", detail="ok"),
        HealthCheck(name="b", status="yellow", detail="warn"),
        HealthCheck(name="c", status="green", detail="ok"),
    ]
    overall = aggregate_health(checks)
    assert overall.status == "yellow"
    assert overall.metric["yellow"] == 1


def test_aggregate_one_red_dominates_even_with_yellow() -> None:
    checks = [
        HealthCheck(name="a", status="yellow", detail="warn"),
        HealthCheck(name="b", status="red", detail="fail"),
        HealthCheck(name="c", status="green", detail="ok"),
    ]
    overall = aggregate_health(checks)
    assert overall.status == "red"
    assert overall.metric == {"green": 1, "yellow": 1, "red": 1, "total": 3}


def test_aggregate_detail_lists_only_non_zero_buckets() -> None:
    """Si tout est green, le detail ne mentionne pas '0 red, 0 yellow'."""
    overall = aggregate_health(
        [HealthCheck(name="a", status="green", detail="ok")],
    )
    assert overall.detail == "1 green"


# =============================================================================
# check_kb_seeded
# =============================================================================
def _make_session_returning_count(count: int) -> MagicMock:
    """Forge une AsyncSession dont ``execute()`` renvoie un résultat dont
    ``.scalar()`` rend ``count``."""
    fake_result = MagicMock()
    fake_result.scalar.return_value = count
    session = MagicMock()
    session.execute = AsyncMock(return_value=fake_result)
    return session


@pytest.mark.asyncio
async def test_kb_seeded_green_when_above_min() -> None:
    session = _make_session_returning_count(93)
    check = await check_kb_seeded(session, min_chunks=50)
    assert check.status == "green"
    assert check.metric["kb_chunk_count"] == 93


@pytest.mark.asyncio
async def test_kb_seeded_yellow_below_min_but_non_zero() -> None:
    session = _make_session_returning_count(20)
    check = await check_kb_seeded(session, min_chunks=50)
    assert check.status == "yellow"
    assert check.metric["kb_chunk_count"] == 20


@pytest.mark.asyncio
async def test_kb_seeded_red_when_zero() -> None:
    session = _make_session_returning_count(0)
    check = await check_kb_seeded(session, min_chunks=50)
    assert check.status == "red"
    assert "vide" in check.detail.lower()


# =============================================================================
# check_agent_freshness
# =============================================================================
def _make_run(agent: str, hours_ago: float, status: str = "success") -> AgentRun:
    started_at = datetime.now(UTC) - timedelta(hours=hours_ago)
    return AgentRun(
        agent_name=agent,
        command=None,
        status=status,
        started_at=started_at,
    )


@pytest.mark.asyncio
async def test_freshness_green_when_all_recent() -> None:
    with patch.object(
        health,
        "get_last_run_per_agent",
        new=AsyncMock(
            return_value={
                "DigestBuilder": _make_run("DigestBuilder", hours_ago=2.0),
                "EmailBot": _make_run("EmailBot", hours_ago=0.5),
                "FinanceBot": _make_run("FinanceBot", hours_ago=4.0),
                "StrategyBot": _make_run("StrategyBot", hours_ago=10.0),
                "OKRTracker": _make_run("OKRTracker", hours_ago=10.0),
                "BoardReporter": _make_run("BoardReporter", hours_ago=24.0),
                "InvoicePredictor": _make_run("InvoicePredictor", hours_ago=10.0),
                "ExpenseAuditor": _make_run("ExpenseAuditor", hours_ago=24.0),
                "TaxBot": _make_run("TaxBot", hours_ago=24.0),
                "ReconcileBot": _make_run("ReconcileBot", hours_ago=10.0),
                "BurnRateMonitor": _make_run("BurnRateMonitor", hours_ago=10.0),
                "VendorContractWatcher": _make_run("VendorContractWatcher", hours_ago=10.0),
                "ProspectMiner": _make_run("ProspectMiner", hours_ago=4.0),
                "LeadEnricher": _make_run("LeadEnricher", hours_ago=4.0)
,
                "OutboundBot": _make_run("OutboundBot", hours_ago=4.0),
                "IntentSignalsBot": _make_run("IntentSignalsBot", hours_ago=4.0),
                "DealRiskScorer": _make_run("DealRiskScorer", hours_ago=24.0),
                "ContentBot": _make_run("ContentBot", hours_ago=1.0),
                "AdBot": _make_run("AdBot", hours_ago=4.0),
                "TrendSpotter": _make_run("TrendSpotter", hours_ago=4.0),
                "SocialAnalytics": _make_run("SocialAnalytics", hours_ago=24.0),
                "BacklinkOutreach": _make_run("BacklinkOutreach", hours_ago=24.0),
                "KeywordRadar": _make_run("KeywordRadar", hours_ago=24.0),
                "LandingOptimizer": _make_run("LandingOptimizer", hours_ago=24.0),
                "WebinarPromoter": _make_run("WebinarPromoter", hours_ago=24.0),
                "TestimonialHunter": _make_run("TestimonialHunter", hours_ago=4.0),
                "NewsletterBot": _make_run("NewsletterBot", hours_ago=24.0),
                "ChurnPredictor": _make_run("ChurnPredictor", hours_ago=4.0),
                "HealthScoreBot": _make_run("HealthScoreBot", hours_ago=4.0),
                "OnboardingBot": _make_run("OnboardingBot", hours_ago=4.0),
                "NPSCollector": _make_run("NPSCollector", hours_ago=4.0),
                "UpsellSpotter": _make_run("UpsellSpotter", hours_ago=4.0),
                "EscalationRouter": _make_run("EscalationRouter", hours_ago=4.0),
                "KBUpdater": _make_run("KBUpdater", hours_ago=24.0),
                "ReviewBot": _make_run("ReviewBot", hours_ago=24.0),
                "BugTriageBot": _make_run("BugTriageBot", hours_ago=4.0),
                "FeedbackAggregator": _make_run("FeedbackAggregator", hours_ago=24.0),
                "ChangelogBot": _make_run("ChangelogBot", hours_ago=24.0),
                "RoadmapPublisher": _make_run("RoadmapPublisher", hours_ago=24.0),
                "UptimeMonitor": _make_run("UptimeMonitor", hours_ago=0.1),
                "DependencyAuditor": _make_run("DependencyAuditor", hours_ago=24.0),
                "LogAnomalyDetector": _make_run("LogAnomalyDetector", hours_ago=4.0),
                "BackupVerifier": _make_run("BackupVerifier", hours_ago=4.0),
                "SSLExpirer": _make_run("SSLExpirer", hours_ago=24.0),
                "DNSGuard": _make_run("DNSGuard", hours_ago=4.0),
                "SecretRotator": _make_run("SecretRotator", hours_ago=24.0),
                "CIFlakeTracker": _make_run("CIFlakeTracker", hours_ago=4.0),
                "CompetitorWatcher": _make_run("CompetitorWatcher", hours_ago=24.0),
                "BreachWatcher": _make_run("BreachWatcher", hours_ago=4.0),
                "RegulatoryWatcher": _make_run("RegulatoryWatcher", hours_ago=4.0),
                "CVEMonitor": _make_run("CVEMonitor", hours_ago=4.0),
                "DarkWebMonitor": _make_run("DarkWebMonitor", hours_ago=4.0),
                "BountyRadar": _make_run("BountyRadar", hours_ago=24.0),
            }
        ),
    ):
        check = await check_agent_freshness(MagicMock())
    assert check.status == "green"


@pytest.mark.asyncio
async def test_freshness_red_when_one_agent_stale() -> None:
    """EmailBot 115h alors que seuil = 14.5h → red."""
    with patch.object(
        health,
        "get_last_run_per_agent",
        new=AsyncMock(
            return_value={
                "DigestBuilder": _make_run("DigestBuilder", hours_ago=2.0),
                "EmailBot": _make_run("EmailBot", hours_ago=115.0),
                "FinanceBot": _make_run("FinanceBot", hours_ago=4.0),
            }
        ),
    ):
        check = await check_agent_freshness(MagicMock())
    assert check.status == "red"
    assert check.metric["per_agent"]["EmailBot"]["status"] == "red"
    assert check.metric["per_agent"]["EmailBot"]["age_hours"] > 100


@pytest.mark.asyncio
async def test_freshness_yellow_at_80_percent_of_threshold() -> None:
    """DigestBuilder threshold=26h ; age=22h → 22/26 > 0.8 → yellow."""
    with patch.object(
        health,
        "get_last_run_per_agent",
        new=AsyncMock(
            return_value={
                "DigestBuilder": _make_run("DigestBuilder", hours_ago=22.0),
                "EmailBot": _make_run("EmailBot", hours_ago=0.5),
                "FinanceBot": _make_run("FinanceBot", hours_ago=4.0),
                "StrategyBot": _make_run("StrategyBot", hours_ago=10.0),
                "OKRTracker": _make_run("OKRTracker", hours_ago=10.0),
                "BoardReporter": _make_run("BoardReporter", hours_ago=24.0),
                "InvoicePredictor": _make_run("InvoicePredictor", hours_ago=10.0),
                "ExpenseAuditor": _make_run("ExpenseAuditor", hours_ago=24.0),
                "TaxBot": _make_run("TaxBot", hours_ago=24.0),
                "ReconcileBot": _make_run("ReconcileBot", hours_ago=10.0),
                "BurnRateMonitor": _make_run("BurnRateMonitor", hours_ago=10.0),
                "VendorContractWatcher": _make_run("VendorContractWatcher", hours_ago=10.0),
                "ProspectMiner": _make_run("ProspectMiner", hours_ago=4.0),
                "LeadEnricher": _make_run("LeadEnricher", hours_ago=4.0),
                "OutboundBot": _make_run("OutboundBot", hours_ago=4.0),
                "IntentSignalsBot": _make_run("IntentSignalsBot", hours_ago=4.0),
                "DealRiskScorer": _make_run("DealRiskScorer", hours_ago=24.0),
                "ContentBot": _make_run("ContentBot", hours_ago=1.0),
                "AdBot": _make_run("AdBot", hours_ago=4.0),
                "TrendSpotter": _make_run("TrendSpotter", hours_ago=4.0),
                "SocialAnalytics": _make_run("SocialAnalytics", hours_ago=24.0),
                "BacklinkOutreach": _make_run("BacklinkOutreach", hours_ago=24.0),
                "KeywordRadar": _make_run("KeywordRadar", hours_ago=24.0),
                "LandingOptimizer": _make_run("LandingOptimizer", hours_ago=24.0),
                "WebinarPromoter": _make_run("WebinarPromoter", hours_ago=24.0),
                "TestimonialHunter": _make_run("TestimonialHunter", hours_ago=4.0),
                "NewsletterBot": _make_run("NewsletterBot", hours_ago=24.0),
                "ChurnPredictor": _make_run("ChurnPredictor", hours_ago=4.0),
                "HealthScoreBot": _make_run("HealthScoreBot", hours_ago=4.0),
                "OnboardingBot": _make_run("OnboardingBot", hours_ago=4.0),
                "NPSCollector": _make_run("NPSCollector", hours_ago=4.0),
                "UpsellSpotter": _make_run("UpsellSpotter", hours_ago=4.0),
                "EscalationRouter": _make_run("EscalationRouter", hours_ago=4.0),
                "KBUpdater": _make_run("KBUpdater", hours_ago=24.0),
                "ReviewBot": _make_run("ReviewBot", hours_ago=24.0),
                "BugTriageBot": _make_run("BugTriageBot", hours_ago=4.0),
                "FeedbackAggregator": _make_run("FeedbackAggregator", hours_ago=24.0),
                "ChangelogBot": _make_run("ChangelogBot", hours_ago=24.0),
                "RoadmapPublisher": _make_run("RoadmapPublisher", hours_ago=24.0),
                "UptimeMonitor": _make_run("UptimeMonitor", hours_ago=0.1),
                "DependencyAuditor": _make_run("DependencyAuditor", hours_ago=24.0),
                "LogAnomalyDetector": _make_run("LogAnomalyDetector", hours_ago=4.0),
                "BackupVerifier": _make_run("BackupVerifier", hours_ago=4.0),
                "SSLExpirer": _make_run("SSLExpirer", hours_ago=24.0),
                "DNSGuard": _make_run("DNSGuard", hours_ago=4.0),
                "SecretRotator": _make_run("SecretRotator", hours_ago=24.0),
                "CIFlakeTracker": _make_run("CIFlakeTracker", hours_ago=4.0),
                "CompetitorWatcher": _make_run("CompetitorWatcher", hours_ago=24.0),
                "BreachWatcher": _make_run("BreachWatcher", hours_ago=4.0),
                "RegulatoryWatcher": _make_run("RegulatoryWatcher", hours_ago=4.0),
                "CVEMonitor": _make_run("CVEMonitor", hours_ago=4.0),
                "DarkWebMonitor": _make_run("DarkWebMonitor", hours_ago=4.0),
                "BountyRadar": _make_run("BountyRadar", hours_ago=24.0),
            }
        ),
    ):
        check = await check_agent_freshness(MagicMock())
    assert check.status == "yellow"
    assert check.metric["per_agent"]["DigestBuilder"]["status"] == "yellow"


@pytest.mark.asyncio
async def test_freshness_red_when_agent_never_ran() -> None:
    """Aucun run en DB pour un agent attendu → red (cas critique)."""
    with patch.object(
        health,
        "get_last_run_per_agent",
        new=AsyncMock(
            return_value={
                "DigestBuilder": _make_run("DigestBuilder", hours_ago=2.0),
                # EmailBot et FinanceBot manquants
            }
        ),
    ):
        check = await check_agent_freshness(MagicMock())
    assert check.status == "red"
    assert check.metric["per_agent"]["EmailBot"]["status"] == "red"
    assert check.metric["per_agent"]["EmailBot"]["age_hours"] is None


@pytest.mark.asyncio
async def test_freshness_respects_custom_thresholds() -> None:
    """Le caller peut passer ses propres seuils par agent."""
    with patch.object(
        health,
        "get_last_run_per_agent",
        new=AsyncMock(
            return_value={"BotX": _make_run("BotX", hours_ago=5.0)},
        ),
    ):
        check = await check_agent_freshness(MagicMock(), max_age_hours={"BotX": 4.0})
    assert check.status == "red"  # 5h > 4h


# =============================================================================
# check_tripped_breakers
# =============================================================================
def _make_breaker(name: str, hours_ago: float | None) -> Breaker:
    tripped_at = datetime.now(UTC) - timedelta(hours=hours_ago) if hours_ago is not None else None
    return Breaker(
        name=name,
        tripped=True,
        tripped_at=tripped_at,
        reason="test reason",
    )


@pytest.mark.asyncio
async def test_tripped_breakers_green_when_none() -> None:
    with patch.object(health, "list_tripped_breakers", new=AsyncMock(return_value=[])):
        check = await check_tripped_breakers(MagicMock())
    assert check.status == "green"
    assert check.metric["tripped_count"] == 0


@pytest.mark.asyncio
async def test_tripped_breakers_yellow_when_recent_trip() -> None:
    """Breaker tripped depuis 1h, seuil=4h → yellow (pas encore stale)."""
    with patch.object(
        health,
        "list_tripped_breakers",
        new=AsyncMock(return_value=[_make_breaker("mrr_drop", hours_ago=1.0)]),
    ):
        check = await check_tripped_breakers(MagicMock(), alert_after_hours=4.0)
    assert check.status == "yellow"
    assert check.metric["tripped_count"] == 1
    assert check.metric["stale_count"] == 0


@pytest.mark.asyncio
async def test_tripped_breakers_red_when_stale() -> None:
    """Breaker tripped depuis 6h, seuil=4h → red."""
    with patch.object(
        health,
        "list_tripped_breakers",
        new=AsyncMock(return_value=[_make_breaker("mrr_drop", hours_ago=6.0)]),
    ):
        check = await check_tripped_breakers(MagicMock(), alert_after_hours=4.0)
    assert check.status == "red"
    assert check.metric["stale_count"] == 1


# =============================================================================
# check_queued_escalations
# =============================================================================
@pytest.mark.asyncio
async def test_queued_green_below_half_threshold() -> None:
    session = _make_session_returning_count(3)
    check = await check_queued_escalations(session, alert_count=20)
    assert check.status == "green"


@pytest.mark.asyncio
async def test_queued_yellow_when_above_half_threshold() -> None:
    """alert=20, queued=11 → 11 > 10 (= 20 // 2) → yellow."""
    session = _make_session_returning_count(11)
    check = await check_queued_escalations(session, alert_count=20)
    assert check.status == "yellow"


@pytest.mark.asyncio
async def test_queued_red_when_above_threshold() -> None:
    session = _make_session_returning_count(25)
    check = await check_queued_escalations(session, alert_count=20)
    assert check.status == "red"


@pytest.mark.asyncio
async def test_queued_default_threshold() -> None:
    """Sanity check du DEFAULT_QUEUED_ALERT_COUNT — change ce test si la
    valeur change intentionnellement."""
    assert DEFAULT_QUEUED_ALERT_COUNT > 0


# =============================================================================
# run_all_checks — un check qui crash devient red, les autres tournent
# =============================================================================
@pytest.mark.asyncio
async def test_run_all_swallows_crash_per_check() -> None:
    """Si check_kb_seeded lève, les autres checks doivent quand même
    tourner et le résultat global doit contenir tous les noms attendus
    (avec le crashed en red)."""

    async def _crash(*args: object, **kwargs: object) -> HealthCheck:
        raise RuntimeError("simulated db hiccup")

    with (
        patch.object(health, "check_db_connectivity", new=_crash),
        patch.object(
            health,
            "check_kb_seeded",
            new=AsyncMock(
                return_value=HealthCheck(name="kb_seeded", status="green", detail="ok"),
            ),
        ),
        patch.object(
            health,
            "check_agent_freshness",
            new=AsyncMock(
                return_value=HealthCheck(name="agent_freshness", status="green", detail="ok"),
            ),
        ),
        patch.object(
            health,
            "check_tripped_breakers",
            new=AsyncMock(
                return_value=HealthCheck(name="tripped_breakers", status="green", detail="ok"),
            ),
        ),
        patch.object(
            health,
            "check_queued_escalations",
            new=AsyncMock(
                return_value=HealthCheck(name="queued_escalations", status="green", detail="ok"),
            ),
        ),
    ):
        checks = await run_all_checks(MagicMock())

    assert len(checks) == 5
    db_check = next(c for c in checks if c.name == "db_connectivity")
    assert db_check.status == "red"
    assert "simulated db hiccup" in db_check.detail
    overall = aggregate_health(checks)
    assert overall.status == "red"
