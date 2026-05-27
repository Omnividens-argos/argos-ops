"""Health checks pour Argos Ops (P19 maintenance & observabilité).

Diagnostic réutilisable : DB up, agents frais (dernier run < seuil),
breakers tripped, file Tier 2 (queued) qui s'accumule, KB seedée.

Sous D-017 (architecture local-first), Argos Ops tourne sur l'ordi du
fondateur — un check de santé doit donc être :
- **Pull-based** (pas de daemon qui pousse en continu)
- **Idempotent** (relançable autant qu'on veut sans effet de bord)
- **Tolérant** aux indispos partielles (un check qui crash n'empêche
  pas les autres de tourner)

Utilisation :
- ``scripts/health_check.py`` — CLI quotidien à mettre en cron (matin
  avant le digest)
- L'endpoint ops dashboard ``GET /health/detailed`` (à câbler en P19.1)
  peut consommer ces mêmes fonctions

Architecture :
- Chaque check retourne un :class:`HealthCheck` immuable
- :func:`run_all_checks` lance toute la batterie **séquentiellement**
  sur la même AsyncSession (SQLAlchemy interdit les ops concurrentes
  sur une session). Swallow les exceptions individuelles — un check
  qui crash devient ``red`` avec l'erreur en detail
- :func:`aggregate_health` applique « worst status wins » + compte les
  checks par statut
"""

from __future__ import annotations

from collections.abc import Awaitable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from loguru import logger
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col

from argos_ops.crm.models import Interaction, KBChunk
from argos_ops.crm.repository import (
    get_last_run_per_agent,
    list_tripped_breakers,
)

HealthStatus = Literal["green", "yellow", "red"]

# Cadences attendues par agent (en heures depuis dernier run réussi).
# Les valeurs viennent des cron actuels (CLAUDE.md § « Task Scheduler actifs ») :
#   - DigestBuilder : 0 8 * * *           → 24h ± 1h slack
#   - EmailBot      : */15 8-22 * * *     → max 1h en jour ; 14h overnight
#   - FinanceBot    : 0 6 * * *           → 24h ± 1h slack
#   - SupportBot    : interactif (slash) → pas de cadence cron, on skip
# Direction & Stratégie (P22.E) — cron via setup_direction_tasks.ps1 :
#   - StrategyBot   : lundi 8h Paris (hebdo)    → 7j + 4h slack
#   - OKRTracker    : lundi 8h Paris (hebdo)    → 7j + 4h slack
#   - BoardReporter : 1er du mois 7h Paris      → 31j + 12h slack
#   - DecisionLogger : interactif (slash) → pas de cadence cron, skip
# Finance & Trésorerie (P22.F) — cron via setup_finance_tasks.ps1 :
#   - InvoicePredictor       : lundi 7h (hebdo)             → 7j + 4h slack
#   - ExpenseAuditor         : 5 du mois 7h (mensuel)       → 31j + 12h slack
#   - TaxBot                 : 15 du mois 7h (mensuel)      → 31j + 12h slack
#   - ReconcileBot           : lundi 7h15 (hebdo)           → 7j + 4h slack
#   - BurnRateMonitor        : lundi 7h30 (hebdo)           → 7j + 4h slack
#   - VendorContractWatcher  : lundi 7h45 (hebdo)           → 7j + 4h slack
# Sales / Commercial (P22.H) — cron via setup_sales_tasks.ps1 :
#   - ProspectMiner    : quotidien 7h          → 26h slack
#   - LeadEnricher     : quotidien 7h15        → 26h slack
#   - OutboundBot      : quotidien 9h          → 26h slack
#   - IntentSignalsBot : quotidien 8h          → 26h slack
#   - DealRiskScorer   : lundi 8h30 (hebdo)    → 172h slack
#   - MeetingBooker    : réactif (slash) → skip cadence
#   - DemoFollowupBot  : réactif (slash) → skip cadence
#   - ProposalBot      : réactif (slash) → skip cadence
#   - ContractGenerator: réactif (slash) → skip cadence
DEFAULT_AGENT_MAX_AGE_HOURS: dict[str, float] = {
    "DigestBuilder": 26.0,
    "EmailBot": 14.5,
    "FinanceBot": 26.0,
    "StrategyBot": 172.0,  # 7j + 4h
    "OKRTracker": 172.0,  # 7j + 4h
    "BoardReporter": 756.0,  # 31j + 12h
    "InvoicePredictor": 172.0,
    "ExpenseAuditor": 756.0,
    "TaxBot": 756.0,
    "ReconcileBot": 172.0,
    "BurnRateMonitor": 172.0,
    "VendorContractWatcher": 172.0,
    "ProspectMiner": 26.0,
    "LeadEnricher": 26.0,
    "OutboundBot": 26.0,
    "IntentSignalsBot": 26.0,
    "DealRiskScorer": 172.0,
    # Marketing & Growth (P22.I) — cron via setup_marketing_tasks.ps1 :
    #   - ContentBot         : */2 8-20 * * *   → 3h slack (publish toutes les 2h en journée)
    #   - AdBot              : quotidien 09:00  → 26h slack
    #   - TrendSpotter       : quotidien 07:30  → 26h slack
    #   - SocialAnalytics    : lundi 09:00 (hebdo) → 172h slack
    #   - BacklinkOutreach   : jeudi 09:00 (hebdo) → 172h slack
    #   - KeywordRadar       : lundi 09:15 (hebdo) → 172h slack
    #   - LandingOptimizer   : mardi 09:00 (hebdo) → 172h slack
    #   - WebinarPromoter    : mercredi 09:00 (hebdo) → 172h slack
    #   - TestimonialHunter  : quotidien 15:00  → 26h slack
    #   - NewsletterBot      : 1er du mois 10:00 (mensuel) → 756h slack
    #   - CaseStudyDrafter   : réactif (slash) → skip cadence
    #   - SEOBot             : réactif (slash + health-check) → skip cadence
    "ContentBot": 3.0,
    "AdBot": 26.0,
    "TrendSpotter": 26.0,
    "SocialAnalytics": 172.0,
    "BacklinkOutreach": 172.0,
    "KeywordRadar": 172.0,
    "LandingOptimizer": 172.0,
    "WebinarPromoter": 172.0,
    "TestimonialHunter": 26.0,
    "NewsletterBot": 756.0,
    # Customer Success & Support (P22.G) — cron via setup_cs_tasks.ps1 :
    #   - ChurnPredictor    : quotidien 09:30          → 26h slack
    #   - HealthScoreBot    : quotidien 09:00          → 26h slack
    #   - OnboardingBot     : quotidien 08:00          → 26h slack
    #   - NPSCollector      : quotidien 09:15          → 26h slack
    #   - UpsellSpotter     : quotidien 09:45          → 26h slack
    #   - EscalationRouter  : quotidien 08:30          → 26h slack
    #   - KBUpdater         : lundi 10:00 (hebdo)      → 172h slack
    #   - ReviewBot         : 1er du mois 10:00 (mensuel) → 756h slack
    #   - SupportBot        : réactif (slash + health-check) → skip cadence
    "ChurnPredictor": 26.0,
    "HealthScoreBot": 26.0,
    "OnboardingBot": 26.0,
    "NPSCollector": 26.0,
    "UpsellSpotter": 26.0,
    "EscalationRouter": 26.0,
    "KBUpdater": 172.0,
    "ReviewBot": 756.0,
    # Produit & R&D (P22.J) — cron via setup_product_tasks.ps1 :
    #   - BugTriageBot       : quotidien 10:00            → 26h slack
    #   - FeedbackAggregator : lundi 11:00 (hebdo)        → 172h slack
    #   - ChangelogBot       : lundi 11:30 (hebdo)        → 172h slack
    #   - ReleaseNotesBot    : reactif (slash) → skip cadence
    #   - RoadmapPublisher   : 1er du mois 11:00 (mensuel) → 756h slack
    "BugTriageBot": 26.0,
    "FeedbackAggregator": 172.0,
    "ChangelogBot": 172.0,
    "RoadmapPublisher": 756.0,
    # Tech / SRE / Sécurité IT (P22.C/D) — cron via setup_watchers_tasks.ps1 :
    #   - UptimeMonitor       : every 5 min                → 1h slack
    #   - DependencyAuditor   : hebdo lundi 07:00          → 172h slack
    #   - LogAnomalyDetector  : quotidien 04:00            → 26h slack
    #   - BackupVerifier      : quotidien 05:00            → 26h slack
    #   - SSLExpirer          : mensuel 1er 06:00          → 756h slack
    #   - DNSGuard            : quotidien 13:00            → 26h slack
    #   - SecretRotator       : hebdo lundi 06:00          → 172h slack
    #   - CIFlakeTracker      : quotidien 21:00 (post-CI)  → 26h slack
    "UptimeMonitor": 1.0,
    "DependencyAuditor": 172.0,
    "LogAnomalyDetector": 26.0,
    "BackupVerifier": 26.0,
    "SSLExpirer": 756.0,
    "DNSGuard": 26.0,
    "SecretRotator": 172.0,
    "CIFlakeTracker": 26.0,
    # Veille & Threat Intelligence (P22.D) — cron via setup_watchers_tasks.ps1 :
    #   - CompetitorWatcher  : lundi 12:00 (hebdo)         → 172h slack
    #   - BreachWatcher      : quotidien 06:30             → 26h slack
    #   - RegulatoryWatcher  : quotidien 07:00             → 26h slack
    #   - CVEMonitor         : quotidien 07:30             → 26h slack
    #   - DarkWebMonitor     : quotidien 12:30             → 26h slack
    #   - BountyRadar        : 1er du mois 12:00 (mensuel) → 756h slack
    "CompetitorWatcher": 172.0,
    "BreachWatcher": 26.0,
    "RegulatoryWatcher": 26.0,
    "CVEMonitor": 26.0,
    "DarkWebMonitor": 26.0,
    "BountyRadar": 756.0,
}

# Default thresholds
DEFAULT_BREAKER_TRIPPED_ALERT_HOURS = 4.0  # cf. plan § 19.3 « 0 breaker actif > 4 h »
DEFAULT_QUEUED_ALERT_COUNT = 20  # > 20 queued en attente = anomalie
DEFAULT_MIN_KB_CHUNKS = 50  # critère P3 plan


@dataclass(frozen=True)
class HealthCheck:
    """Résultat immuable d'un check unitaire."""

    name: str
    status: HealthStatus
    detail: str
    metric: dict[str, Any] = field(default_factory=dict)


# =============================================================================
# Checks unitaires
# =============================================================================
async def check_db_connectivity(session: AsyncSession) -> HealthCheck:
    """Ping simple : SELECT 1. Si ça lève, DB down → red."""
    try:
        result = await session.execute(select(func.count()).select_from(KBChunk))
        chunk_count = int(result.scalar() or 0)
    except Exception as exc:
        return HealthCheck(
            name="db_connectivity",
            status="red",
            detail=f"DB inaccessible : {type(exc).__name__}: {exc}",
        )
    return HealthCheck(
        name="db_connectivity",
        status="green",
        detail=f"DB up — {chunk_count} chunks indexés",
        metric={"kb_chunk_count": chunk_count},
    )


async def check_kb_seeded(
    session: AsyncSession,
    *,
    min_chunks: int = DEFAULT_MIN_KB_CHUNKS,
) -> HealthCheck:
    """Vérifie que la KB contient au moins ``min_chunks`` chunks indexés.

    Sanity check anti-régression : si quelqu'un fait ``TRUNCATE kb_chunks``
    par erreur, SupportBot / ContentBot / OutboundBot vont halluciner
    massivement.
    """
    result = await session.execute(select(func.count()).select_from(KBChunk))
    count = int(result.scalar() or 0)

    if count == 0:
        return HealthCheck(
            name="kb_seeded",
            status="red",
            detail="KB vide — relance `uv run python scripts/seed_kb.py`",
            metric={"kb_chunk_count": 0, "min_expected": min_chunks},
        )
    if count < min_chunks:
        return HealthCheck(
            name="kb_seeded",
            status="yellow",
            detail=f"KB sous-seedée : {count} chunks (min attendu {min_chunks})",
            metric={"kb_chunk_count": count, "min_expected": min_chunks},
        )
    return HealthCheck(
        name="kb_seeded",
        status="green",
        detail=f"KB seedée — {count} chunks",
        metric={"kb_chunk_count": count, "min_expected": min_chunks},
    )


async def check_agent_freshness(
    session: AsyncSession,
    *,
    max_age_hours: dict[str, float] | None = None,
) -> HealthCheck:
    """Vérifie que chaque agent attendu a un run récent.

    Pour chaque agent listé dans ``max_age_hours`` :
    - red si aucun run en DB sur les 30 derniers jours (cf.
      ``get_last_run_per_agent``)
    - red si dernier run > seuil
    - yellow si dernier run > 80 % du seuil (early warning)
    - green sinon

    Le statut global = pire statut individuel.
    """
    max_age_hours = max_age_hours or DEFAULT_AGENT_MAX_AGE_HOURS
    last_runs = await get_last_run_per_agent(session)
    now = datetime.now(UTC)
    per_agent: dict[str, dict[str, Any]] = {}
    worst: HealthStatus = "green"

    for agent_name, threshold_h in max_age_hours.items():
        run = last_runs.get(agent_name)
        if run is None or run.started_at is None:
            per_agent[agent_name] = {
                "status": "red",
                "age_hours": None,
                "threshold_hours": threshold_h,
                "last_run_status": None,
            }
            worst = "red"
            continue

        started = run.started_at
        if started.tzinfo is None:
            started = started.replace(tzinfo=UTC)
        age_hours = (now - started).total_seconds() / 3600.0
        warn_threshold = threshold_h * 0.8

        if age_hours > threshold_h:
            agent_status: HealthStatus = "red"
            worst = "red"
        elif age_hours > warn_threshold:
            agent_status = "yellow"
            worst = "red" if worst == "red" else "yellow"
        else:
            agent_status = "green"

        per_agent[agent_name] = {
            "status": agent_status,
            "age_hours": round(age_hours, 2),
            "threshold_hours": threshold_h,
            "last_run_status": run.status,
        }

    summary_parts = [
        f"{name}={data['status']}"
        + (f" (last={data['age_hours']}h)" if data["age_hours"] is not None else " (no run)")
        for name, data in per_agent.items()
    ]
    return HealthCheck(
        name="agent_freshness",
        status=worst,
        detail=", ".join(summary_parts),
        metric={"per_agent": per_agent},
    )


async def check_tripped_breakers(
    session: AsyncSession,
    *,
    alert_after_hours: float = DEFAULT_BREAKER_TRIPPED_ALERT_HOURS,
) -> HealthCheck:
    """Liste les breakers tripped + flag ceux trippés depuis > seuil.

    Tout breaker tripped déclenche au moins ``yellow``. ``red`` si au
    moins un breaker est tripped depuis > ``alert_after_hours``
    (=« 0 breaker actif > 4 h » du plan § 19.3).
    """
    tripped = await list_tripped_breakers(session)
    now = datetime.now(UTC)

    if not tripped:
        return HealthCheck(
            name="tripped_breakers",
            status="green",
            detail="Aucun breaker tripped",
            metric={"tripped_count": 0},
        )

    stale_count = 0
    rows: list[dict[str, Any]] = []
    for br in tripped:
        tripped_at = br.tripped_at
        age_hours: float | None = None
        if tripped_at is not None:
            ts = tripped_at if tripped_at.tzinfo else tripped_at.replace(tzinfo=UTC)
            age_hours = (now - ts).total_seconds() / 3600.0
            if age_hours > alert_after_hours:
                stale_count += 1
        rows.append(
            {
                "name": br.name,
                "age_hours": round(age_hours, 2) if age_hours is not None else None,
                "reason": br.reason,
            }
        )

    status: HealthStatus = "red" if stale_count else "yellow"
    detail = f"{len(tripped)} breaker(s) tripped" + (
        f" (dont {stale_count} > {alert_after_hours}h)" if stale_count else ""
    )
    return HealthCheck(
        name="tripped_breakers",
        status=status,
        detail=detail,
        metric={
            "tripped_count": len(tripped),
            "stale_count": stale_count,
            "alert_threshold_hours": alert_after_hours,
            "breakers": rows,
        },
    )


async def check_queued_escalations(
    session: AsyncSession,
    *,
    alert_count: int = DEFAULT_QUEUED_ALERT_COUNT,
    window_hours: int = 48,
) -> HealthCheck:
    """Compte les interactions en file Tier 2 (``judge_verdict='queued'``)
    sur la fenêtre temporelle.

    > yellow si > alert_count/2 ; red si > alert_count.
    Le breaker ``support_low_confidence`` (P15 § 15.1) trip à 50 items,
    donc on alerte avant ça.
    """
    cutoff = datetime.now(UTC) - timedelta(hours=window_hours)
    stmt = (
        select(func.count())
        .select_from(Interaction)
        .where(col(Interaction.judge_verdict) == "queued")
        .where(col(Interaction.occurred_at) >= cutoff)
    )
    queued = int((await session.execute(stmt)).scalar() or 0)

    if queued > alert_count:
        status: HealthStatus = "red"
    elif queued > alert_count // 2:
        status = "yellow"
    else:
        status = "green"
    return HealthCheck(
        name="queued_escalations",
        status=status,
        detail=f"{queued} interaction(s) queued sur les {window_hours} dernières heures",
        metric={
            "queued_count": queued,
            "alert_threshold": alert_count,
            "window_hours": window_hours,
        },
    )


# =============================================================================
# Agrégation + lancement parallèle
# =============================================================================
async def _safe_run(
    name: str,
    coro: Awaitable[HealthCheck],
) -> HealthCheck:
    """Wrappe un check pour qu'une exception se transforme en check red."""
    try:
        return await coro
    except Exception as exc:
        logger.exception(f"Health check {name} a crashé")
        return HealthCheck(
            name=name,
            status="red",
            detail=f"check crashé : {type(exc).__name__}: {exc}",
        )


async def run_all_checks(session: AsyncSession) -> list[HealthCheck]:
    """Lance toute la batterie de checks **séquentiellement** sur la
    même session. SQLAlchemy AsyncSession n'autorise pas les ops
    concurrentes (provisioning_lock), donc pas d'``asyncio.gather`` ici.
    Le coût d'exécution reste de l'ordre de la seconde — pas de besoin
    de paralléliser.

    Aucune exception ne remonte — un check qui crash devient ``red``
    avec l'erreur en detail. Garantit que le diagnostic est complet
    même en cas de panne partielle.
    """
    return [
        await _safe_run("db_connectivity", check_db_connectivity(session)),
        await _safe_run("kb_seeded", check_kb_seeded(session)),
        await _safe_run("agent_freshness", check_agent_freshness(session)),
        await _safe_run("tripped_breakers", check_tripped_breakers(session)),
        await _safe_run("queued_escalations", check_queued_escalations(session)),
    ]


_STATUS_RANK: dict[HealthStatus, int] = {"green": 0, "yellow": 1, "red": 2}


def aggregate_health(checks: list[HealthCheck]) -> HealthCheck:
    """Statut global = pire statut individuel (worst wins).

    Cas vide → green (rien à juger). On retourne un :class:`HealthCheck`
    synthétique avec le compte par statut dans ``metric`` pour faciliter
    le formatage CLI / embed.
    """
    if not checks:
        return HealthCheck(
            name="overall",
            status="green",
            detail="Aucun check exécuté",
            metric={"green": 0, "yellow": 0, "red": 0, "total": 0},
        )

    worst: HealthStatus = "green"
    counts = {"green": 0, "yellow": 0, "red": 0}
    for check in checks:
        counts[check.status] += 1
        if _STATUS_RANK[check.status] > _STATUS_RANK[worst]:
            worst = check.status

    detail_parts = [f"{counts['green']} green"]
    if counts["yellow"]:
        detail_parts.append(f"{counts['yellow']} yellow")
    if counts["red"]:
        detail_parts.append(f"{counts['red']} red")
    return HealthCheck(
        name="overall",
        status=worst,
        detail=", ".join(detail_parts),
        metric={**counts, "total": len(checks)},
    )


__all__ = [
    "DEFAULT_AGENT_MAX_AGE_HOURS",
    "DEFAULT_BREAKER_TRIPPED_ALERT_HOURS",
    "DEFAULT_MIN_KB_CHUNKS",
    "DEFAULT_QUEUED_ALERT_COUNT",
    "HealthCheck",
    "HealthStatus",
    "aggregate_health",
    "check_agent_freshness",
    "check_db_connectivity",
    "check_kb_seeded",
    "check_queued_escalations",
    "check_tripped_breakers",
    "run_all_checks",
]
