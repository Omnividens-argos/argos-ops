"""BotHealthBot — SRE de la flotte Argos Ops (P22.B Meta-Ops core).

Surveille uptime + freshness de chaque agent actif. Pour chaque bot du
catalogue Python :
- ``last_run_at`` (dernier run en DB)
- ``last_run_status`` (success / failed / killed_by_breaker / skipped_*)
- durée moyenne sur 7 j
- flag ``stale`` si pas de run depuis ``max_age_hours`` (paramétrable
  par agent, defaults dans :mod:`argos_ops.health`)

Politique de notification (anti-spam) :
- **Silence** si tout est vert (Discord ne reçoit rien)
- **Embed jaune** si ≥1 agent est ``stale`` (jamais run, ou en retard)
- **Embed rouge** si ≥1 agent a un ``last_run_status`` en échec sur 24h,
  ou si ≥1 breaker est tripped

Mutualisation : on importe :func:`argos_ops.health.check_agent_freshness`
et :func:`argos_ops.health.check_tripped_breakers` plutôt que de
dupliquer la logique. BotHealthBot raffine simplement le rendu et la
politique « silence vert » (vs ``scripts/health_check.py`` qui est un
diagnostic complet quotidien et émet un embed même si tout va bien).

Cf. plan ``docs/ARGOS_OPS_PLAN.md`` Annexe D § 12 Meta-Ops, Sprint 1.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col

from argos_ops.agents._watcher_base import (
    color_title,
    emit_alert_or_silence,
    format_age,
    format_duration,
)
from argos_ops.agents.base import BaseAgent, RunResult
from argos_ops.crm.db import session_scope
from argos_ops.crm.models import AgentRun, Breaker
from argos_ops.crm.repository import (
    get_last_run_per_agent,
    list_tripped_breakers,
)
from argos_ops.health import DEFAULT_AGENT_MAX_AGE_HOURS
from argos_ops.notifications.discord import (
    GREEN,
    RED,
    YELLOW,
    Embed,
    EmbedField,
)

AgentHealthStatus = Literal["ok", "stale", "error"]

ERROR_STATUSES: frozenset[str] = frozenset({"failed", "killed_by_breaker"})
LOOKBACK_DURATION_DAYS = 7
ERROR_WINDOW_HOURS = 24


@dataclass(frozen=True)
class BotHealthSnapshot:
    """Photo de santé d'un agent à un instant t."""

    agent_name: str
    last_run_at: datetime | None
    last_run_status: str | None
    avg_duration_seconds_7d: float | None
    age_hours: float | None
    threshold_hours: float
    recent_errors_24h: int
    status: AgentHealthStatus  # ok | stale | error


@dataclass(frozen=True)
class BotHealthReport:
    """Résultat agrégé du run BotHealthBot."""

    snapshots: list[BotHealthSnapshot]
    tripped_breakers: list[Breaker]
    should_alert: bool
    alert_color: int
    summary: str


# =============================================================================
# Collecte
# =============================================================================
async def _avg_duration_seconds(
    session: AsyncSession, agent_name: str, *, since: datetime
) -> float | None:
    """Moyenne de ``ended_at - started_at`` (secondes) sur la fenêtre.

    Ne compte que les runs terminés (``ended_at IS NOT NULL``). Renvoie
    ``None`` si aucun run terminé sur la fenêtre — évite la fausse
    précision « 0.0 ».
    """
    stmt = (
        select(func.avg(func.extract("epoch", col(AgentRun.ended_at) - col(AgentRun.started_at))))
        .where(col(AgentRun.agent_name) == agent_name)
        .where(col(AgentRun.started_at) >= since)
        .where(col(AgentRun.ended_at).is_not(None))
    )
    avg = (await session.execute(stmt)).scalar()
    return float(avg) if avg is not None else None


async def _count_recent_errors(session: AsyncSession, agent_name: str, *, since: datetime) -> int:
    """Compte les runs en échec (``failed``, ``killed_by_breaker``)
    sur la fenêtre."""
    stmt = (
        select(func.count())
        .select_from(AgentRun)
        .where(col(AgentRun.agent_name) == agent_name)
        .where(col(AgentRun.status).in_(list(ERROR_STATUSES)))
        .where(col(AgentRun.started_at) >= since)
    )
    return int((await session.execute(stmt)).scalar() or 0)


async def collect_snapshots(
    session: AsyncSession,
    *,
    agent_names: Iterable[str],
    max_age_hours: dict[str, float] | None = None,
    now: datetime | None = None,
) -> list[BotHealthSnapshot]:
    """Construit un :class:`BotHealthSnapshot` par agent attendu.

    ``agent_names`` doit lister les bots actifs dont on attend une
    cadence régulière (ex : ``["DigestBuilder", "EmailBot", "FinanceBot"]``).
    Les agents interactifs (SupportBot) n'ont pas de cadence cron et
    doivent être omis de cette liste.

    Le statut individuel est calculé ainsi :
    - ``error`` si ≥1 échec dans les 24 dernières heures
    - ``stale`` si jamais run en DB OU si ``age_hours > threshold``
    - ``ok`` sinon
    """
    max_age_hours = max_age_hours or DEFAULT_AGENT_MAX_AGE_HOURS
    now = now or datetime.now(UTC)
    error_cutoff = now - timedelta(hours=ERROR_WINDOW_HOURS)
    duration_cutoff = now - timedelta(days=LOOKBACK_DURATION_DAYS)

    last_runs = await get_last_run_per_agent(session)
    snapshots: list[BotHealthSnapshot] = []

    for agent_name in agent_names:
        threshold = max_age_hours.get(agent_name, 24.0)
        last_run = last_runs.get(agent_name)
        avg_duration = await _avg_duration_seconds(session, agent_name, since=duration_cutoff)
        recent_errors = await _count_recent_errors(session, agent_name, since=error_cutoff)

        last_run_at: datetime | None = None
        last_run_status: str | None = None
        age_hours: float | None = None

        if last_run is not None and last_run.started_at is not None:
            started = last_run.started_at
            if started.tzinfo is None:
                started = started.replace(tzinfo=UTC)
            last_run_at = started
            last_run_status = last_run.status
            age_hours = (now - started).total_seconds() / 3600.0

        # Priorité : error > stale > ok
        status: AgentHealthStatus
        if recent_errors > 0:
            status = "error"
        elif age_hours is None or age_hours > threshold:
            status = "stale"
        else:
            status = "ok"

        snapshots.append(
            BotHealthSnapshot(
                agent_name=agent_name,
                last_run_at=last_run_at,
                last_run_status=last_run_status,
                avg_duration_seconds_7d=avg_duration,
                age_hours=round(age_hours, 2) if age_hours is not None else None,
                threshold_hours=threshold,
                recent_errors_24h=recent_errors,
                status=status,
            )
        )

    return snapshots


# =============================================================================
# Décision d'alerte
# =============================================================================
_STATUS_ICON: dict[AgentHealthStatus, str] = {
    "ok": "[OK]",
    "stale": "[STALE]",
    "error": "[ERR]",
}


def build_report(
    snapshots: list[BotHealthSnapshot],
    tripped: list[Breaker],
) -> BotHealthReport:
    """Agrège snapshots + breakers en :class:`BotHealthReport`.

    Politique : alert dès qu'au moins un agent n'est pas ``ok`` OU
    qu'au moins un breaker est tripped. Couleur rouge si erreur ou
    breaker, jaune si juste du stale, vert sinon (silence côté Discord).
    """
    has_error = any(s.status == "error" for s in snapshots) or bool(tripped)
    has_stale = any(s.status == "stale" for s in snapshots)
    should_alert = has_error or has_stale

    if has_error:
        alert_color = RED
    elif has_stale:
        alert_color = YELLOW
    else:
        alert_color = GREEN

    ok_count = sum(1 for s in snapshots if s.status == "ok")
    stale_count = sum(1 for s in snapshots if s.status == "stale")
    error_count = sum(1 for s in snapshots if s.status == "error")
    breaker_part = f" · {len(tripped)} breaker(s) tripped" if tripped else ""
    summary = f"{ok_count} ok · {stale_count} stale · {error_count} error{breaker_part}"

    return BotHealthReport(
        snapshots=snapshots,
        tripped_breakers=tripped,
        should_alert=should_alert,
        alert_color=alert_color,
        summary=summary,
    )


# =============================================================================
# Formatting
# =============================================================================
def _format_snapshot_value(snap: BotHealthSnapshot) -> str:
    parts = [
        f"last={format_age(snap.age_hours)}",
        f"status={snap.last_run_status or 'n/a'}",
        f"avg7d={format_duration(snap.avg_duration_seconds_7d)}",
    ]
    if snap.recent_errors_24h > 0:
        parts.append(f"errors24h={snap.recent_errors_24h}")
    if snap.status == "stale" and snap.age_hours is not None:
        parts.append(f"threshold={snap.threshold_hours}h")
    return " · ".join(parts)


def build_health_embed(report: BotHealthReport, *, now: datetime | None = None) -> Embed:
    """Construit l'embed Discord — un field par agent + un field breakers
    si nécessaire."""
    now = now or datetime.now(UTC)

    fields: list[EmbedField] = []
    for snap in report.snapshots:
        fields.append(
            EmbedField(
                name=f"{_STATUS_ICON[snap.status]} {snap.agent_name}",
                value=_format_snapshot_value(snap),
                inline=False,
            )
        )

    if report.tripped_breakers:
        breaker_lines = [
            f"- {br.name}" + (f" : {br.reason}" if br.reason else "")
            for br in report.tripped_breakers
        ]
        fields.append(
            EmbedField(
                name="Breakers tripped",
                value="\n".join(breaker_lines)[:1020],
                inline=False,
            )
        )

    title_status = color_title(report.alert_color, green=GREEN, yellow=YELLOW, red=RED)
    return Embed(
        title=f"BotHealthBot — {title_status}",
        description=report.summary,
        color=report.alert_color,
        fields=fields,
        footer="Argos Ops • BotHealthBot",
        timestamp=now.isoformat(),
    )


# =============================================================================
# Agent
# =============================================================================
# Catalogue Python des agents avec cadence cron attendue. Reste
# volontairement minimal et indépendant du frontend `agentCatalog.ts` :
# côté Python on n'a besoin que des bots qui ont une cadence régulière
# (SupportBot interactif est omis). À enrichir quand un nouveau bot
# planifié rejoint la flotte.
MONITORED_AGENTS: tuple[str, ...] = (
    "DigestBuilder",
    "EmailBot",
    "FinanceBot",
)


class BotHealthBot(BaseAgent):
    """SRE de la flotte — surveille uptime + erreurs des bots actifs."""

    name = "BotHealthBot"
    command = "/run-bot-health"
    breaker_name = None  # pas de breaker dédié : c'est lui qui les observe

    def __init__(
        self,
        *,
        agent_names: Iterable[str] | None = None,
        max_age_hours: dict[str, float] | None = None,
    ) -> None:
        self._agent_names = tuple(agent_names or MONITORED_AGENTS)
        self._max_age_hours = max_age_hours

    async def run(self) -> RunResult:
        async with session_scope() as session:
            snapshots = await collect_snapshots(
                session,
                agent_names=self._agent_names,
                max_age_hours=self._max_age_hours,
            )
            tripped = await list_tripped_breakers(session)

        report = build_report(snapshots, tripped)
        return await emit_alert_or_silence(
            report, embed_builder=build_health_embed, agent_name=self.name
        )


__all__ = [
    "ERROR_STATUSES",
    "ERROR_WINDOW_HOURS",
    "LOOKBACK_DURATION_DAYS",
    "MONITORED_AGENTS",
    "AgentHealthStatus",
    "BotHealthBot",
    "BotHealthReport",
    "BotHealthSnapshot",
    "build_health_embed",
    "build_report",
    "collect_snapshots",
]
