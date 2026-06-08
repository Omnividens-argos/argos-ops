"""BotPerfAnalyzer — Performance Engineer de la flotte (P22.C Meta-Ops Sprint 2).

Surveille la **latence** (durée P50 / P95) et le **taux d'erreur** de
chaque agent monitoré sur une fenêtre courte (7 j courants), comparés à
une fenêtre baseline (7 j précédents, J-14 → J-7).

Politique anti-spam (cohérente avec ``BotHealthBot``) :
- **Silence** Discord si aucune régression
- **Embed jaune** si ≥1 régression « warn » détectée (P95 entre 1.5x et 2x
  baseline OU error_rate entre 1.5x et 2x baseline)
- **Embed rouge** si ≥1 régression critique (≥2x baseline)

On utilise la même politique de seuil multiplicatif pour la latence et
les erreurs : un facteur 2 sur la durée comme sur le taux d'erreur est
le signal canonique d'une dérive (cf. plan Annexe D § 12 Sprint 2).

Mutualise avec BotHealthBot la liste ``MONITORED_AGENTS`` (re-exportée
ici) pour éviter de désynchroniser deux catalogues d'agents observés.

Cf. plan ``docs/ARGOS_OPS_PLAN.md`` Annexe D § 12 Meta-Ops, Sprint 2.
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
    format_duration,
    format_rate,
)
from argos_ops.agents.base import BaseAgent, IOItem, RunResult
from argos_ops.agents.bot_health import ERROR_STATUSES, MONITORED_AGENTS
from argos_ops.crm.db import session_scope
from argos_ops.crm.models import AgentRun
from argos_ops.notifications.discord import (
    GREEN,
    RED,
    YELLOW,
    Embed,
    EmbedField,
)

PerfStatus = Literal["ok", "warn", "regression"]

WINDOW_DAYS = 7
WARN_FACTOR = 1.5
REGRESSION_FACTOR = 2.0
MIN_SAMPLE_SIZE = 5  # en deçà, on ne compare pas (trop de bruit)


@dataclass(frozen=True)
class PerfStats:
    """Statistiques de performance d'un agent sur une fenêtre temporelle."""

    p50_seconds: float | None
    p95_seconds: float | None
    error_rate: float | None  # 0.0 à 1.0
    sample_size: int


@dataclass(frozen=True)
class PerfSnapshot:
    """Comparaison fenêtre courante vs baseline pour un agent."""

    agent_name: str
    current: PerfStats
    baseline: PerfStats
    p95_ratio: float | None  # current.p95 / baseline.p95
    error_ratio: float | None  # current.error_rate / baseline.error_rate
    status: PerfStatus
    reason: str  # explication 1 ligne lisible humain


@dataclass(frozen=True)
class PerfReport:
    """Résultat agrégé du run BotPerfAnalyzer."""

    snapshots: list[PerfSnapshot]
    should_alert: bool
    alert_color: int
    summary: str


# =============================================================================
# Calcul des stats
# =============================================================================
async def _percentile_duration(
    session: AsyncSession,
    agent_name: str,
    *,
    since: datetime,
    until: datetime,
    percentile: float,
) -> float | None:
    """Percentile Postgres ``percentile_cont`` sur ``ended_at - started_at``.

    Renvoie ``None`` si la fenêtre ne contient aucun run terminé.
    """
    epoch = func.extract("epoch", col(AgentRun.ended_at) - col(AgentRun.started_at))
    stmt = (
        select(func.percentile_cont(percentile).within_group(epoch))
        .where(col(AgentRun.agent_name) == agent_name)
        .where(col(AgentRun.started_at) >= since)
        .where(col(AgentRun.started_at) < until)
        .where(col(AgentRun.ended_at).is_not(None))
    )
    value = (await session.execute(stmt)).scalar()
    return float(value) if value is not None else None


async def _compute_stats(
    session: AsyncSession,
    agent_name: str,
    *,
    since: datetime,
    until: datetime,
) -> PerfStats:
    """Construit les :class:`PerfStats` pour un agent sur une fenêtre.

    Une seule requête de comptage suffit pour ``sample_size`` et
    ``error_rate`` (les percentiles sont calculés à part car ils
    excluent les runs sans ``ended_at``).
    """
    stmt_total = (
        select(func.count())
        .select_from(AgentRun)
        .where(col(AgentRun.agent_name) == agent_name)
        .where(col(AgentRun.started_at) >= since)
        .where(col(AgentRun.started_at) < until)
    )
    sample_size = int((await session.execute(stmt_total)).scalar() or 0)

    if sample_size == 0:
        return PerfStats(p50_seconds=None, p95_seconds=None, error_rate=None, sample_size=0)

    stmt_errors = (
        select(func.count())
        .select_from(AgentRun)
        .where(col(AgentRun.agent_name) == agent_name)
        .where(col(AgentRun.status).in_(list(ERROR_STATUSES)))
        .where(col(AgentRun.started_at) >= since)
        .where(col(AgentRun.started_at) < until)
    )
    errors = int((await session.execute(stmt_errors)).scalar() or 0)
    error_rate = errors / sample_size if sample_size > 0 else None

    p50 = await _percentile_duration(
        session, agent_name, since=since, until=until, percentile=0.50
    )
    p95 = await _percentile_duration(
        session, agent_name, since=since, until=until, percentile=0.95
    )
    return PerfStats(
        p50_seconds=p50,
        p95_seconds=p95,
        error_rate=error_rate,
        sample_size=sample_size,
    )


# =============================================================================
# Comparaison + verdict
# =============================================================================
def _ratio(current: float | None, baseline: float | None) -> float | None:
    """Ratio current/baseline. None si baseline absent ou nul."""
    if current is None or baseline is None or baseline <= 0:
        return None
    return current / baseline


def _classify(p95_ratio: float | None, error_ratio: float | None) -> tuple[PerfStatus, str]:
    """Détermine le statut + raison à partir des deux ratios.

    Priorité : regression > warn > ok. La pire des deux dimensions
    (latence ou erreur) impose le verdict global.
    """
    reasons: list[str] = []
    worst: PerfStatus = "ok"

    if p95_ratio is not None:
        if p95_ratio >= REGRESSION_FACTOR:
            worst = "regression"
            reasons.append(f"P95 x{p95_ratio:.2f}")
        elif p95_ratio >= WARN_FACTOR:
            if worst != "regression":
                worst = "warn"
            reasons.append(f"P95 x{p95_ratio:.2f}")

    if error_ratio is not None:
        if error_ratio >= REGRESSION_FACTOR:
            worst = "regression"
            reasons.append(f"err_rate x{error_ratio:.2f}")
        elif error_ratio >= WARN_FACTOR and worst != "regression":
            worst = "warn"
            reasons.append(f"err_rate x{error_ratio:.2f}")

    reason = " · ".join(reasons) if reasons else "stable"
    return worst, reason


async def collect_snapshots(
    session: AsyncSession,
    *,
    agent_names: Iterable[str],
    now: datetime | None = None,
    window_days: int = WINDOW_DAYS,
) -> list[PerfSnapshot]:
    """Construit un :class:`PerfSnapshot` par agent.

    Fenêtre courante : ``now - window_days`` → ``now``
    Fenêtre baseline : ``now - 2*window_days`` → ``now - window_days``

    Si une des deux fenêtres a < :data:`MIN_SAMPLE_SIZE` runs, on
    classe ``ok`` avec la raison "insufficient samples" — on évite les
    faux positifs sur un agent qui démarre tout juste.
    """
    now = now or datetime.now(UTC)
    current_start = now - timedelta(days=window_days)
    baseline_start = now - timedelta(days=2 * window_days)

    snapshots: list[PerfSnapshot] = []
    for agent_name in agent_names:
        current = await _compute_stats(session, agent_name, since=current_start, until=now)
        baseline = await _compute_stats(
            session, agent_name, since=baseline_start, until=current_start
        )

        if current.sample_size < MIN_SAMPLE_SIZE or baseline.sample_size < MIN_SAMPLE_SIZE:
            snapshots.append(
                PerfSnapshot(
                    agent_name=agent_name,
                    current=current,
                    baseline=baseline,
                    p95_ratio=None,
                    error_ratio=None,
                    status="ok",
                    reason=(
                        f"insufficient samples (current={current.sample_size}, "
                        f"baseline={baseline.sample_size})"
                    ),
                )
            )
            continue

        p95_ratio = _ratio(current.p95_seconds, baseline.p95_seconds)
        error_ratio = _ratio(current.error_rate, baseline.error_rate)
        status, reason = _classify(p95_ratio, error_ratio)

        snapshots.append(
            PerfSnapshot(
                agent_name=agent_name,
                current=current,
                baseline=baseline,
                p95_ratio=round(p95_ratio, 2) if p95_ratio is not None else None,
                error_ratio=round(error_ratio, 2) if error_ratio is not None else None,
                status=status,
                reason=reason,
            )
        )

    return snapshots


def build_report(snapshots: list[PerfSnapshot]) -> PerfReport:
    """Agrège les snapshots en :class:`PerfReport` avec verdict global."""
    has_regression = any(s.status == "regression" for s in snapshots)
    has_warn = any(s.status == "warn" for s in snapshots)
    should_alert = has_regression or has_warn

    if has_regression:
        alert_color = RED
    elif has_warn:
        alert_color = YELLOW
    else:
        alert_color = GREEN

    ok_count = sum(1 for s in snapshots if s.status == "ok")
    warn_count = sum(1 for s in snapshots if s.status == "warn")
    reg_count = sum(1 for s in snapshots if s.status == "regression")
    summary = f"{ok_count} ok · {warn_count} warn · {reg_count} regression"

    return PerfReport(
        snapshots=snapshots,
        should_alert=should_alert,
        alert_color=alert_color,
        summary=summary,
    )


# =============================================================================
# Formatting
# =============================================================================
_STATUS_ICON: dict[PerfStatus, str] = {
    "ok": "[OK]",
    "warn": "[WARN]",
    "regression": "[REG]",
}


def _format_snapshot_value(snap: PerfSnapshot) -> str:
    parts = [
        f"P95 {format_duration(snap.current.p95_seconds)}"
        f" (baseline {format_duration(snap.baseline.p95_seconds)})",
        f"err {format_rate(snap.current.error_rate)}"
        f" (baseline {format_rate(snap.baseline.error_rate)})",
        f"n={snap.current.sample_size}/{snap.baseline.sample_size}",
    ]
    if snap.reason and snap.status != "ok":
        parts.append(snap.reason)
    return " · ".join(parts)


def build_perf_embed(report: PerfReport, *, now: datetime | None = None) -> Embed:
    """Construit l'embed Discord — un field par agent."""
    now = now or datetime.now(UTC)
    fields = [
        EmbedField(
            name=f"{_STATUS_ICON[snap.status]} {snap.agent_name}",
            value=_format_snapshot_value(snap),
            inline=False,
        )
        for snap in report.snapshots
    ]
    title_status = color_title(report.alert_color, green=GREEN, yellow=YELLOW, red=RED)
    return Embed(
        title=f"BotPerfAnalyzer — {title_status}",
        description=report.summary,
        color=report.alert_color,
        fields=fields,
        footer="Argos Ops • BotPerfAnalyzer",
        timestamp=now.isoformat(),
    )


# =============================================================================
# Agent
# =============================================================================
class BotPerfAnalyzer(BaseAgent):
    """Performance Engineer — surveille latence + taux d'erreur des bots."""

    name = "BotPerfAnalyzer"
    command = "/run-bot-perf"
    breaker_name = None
    ai_act_risk_class = "minimal"

    def __init__(self, *, agent_names: Iterable[str] | None = None) -> None:
        self._agent_names = tuple(agent_names or MONITORED_AGENTS)

    async def run(self) -> RunResult:
        async with session_scope() as session:
            snapshots = await collect_snapshots(session, agent_names=self._agent_names)
        report = build_report(snapshots)
        regressions = [s for s in snapshots if s.status == "regression"]
        warns = [s for s in snapshots if s.status == "warn"]
        inputs = [
            IOItem(
                label="Durées + erreurs des agents",
                kind="db",
                detail="agent_runs (fenêtre 7j courante vs baseline J-14→J-7)",
                count=len(snapshots),
            )
        ]
        outputs = [
            IOItem(
                label="Agents en régression (>=2x baseline)",
                kind="other",
                detail=", ".join(f"{s.agent_name} ({s.reason})" for s in regressions)
                or None,
                count=len(regressions),
            ),
            IOItem(
                label="Agents en dérive (>=1.5x baseline)",
                kind="other",
                detail=", ".join(f"{s.agent_name} ({s.reason})" for s in warns) or None,
                count=len(warns),
            ),
        ]
        return await emit_alert_or_silence(
            report,
            embed_builder=build_perf_embed,
            agent_name=self.name,
            inputs=inputs,
            outputs=outputs,
        )


__all__ = [
    "MIN_SAMPLE_SIZE",
    "REGRESSION_FACTOR",
    "WARN_FACTOR",
    "WINDOW_DAYS",
    "BotPerfAnalyzer",
    "PerfReport",
    "PerfSnapshot",
    "PerfStats",
    "PerfStatus",
    "build_perf_embed",
    "build_report",
    "collect_snapshots",
]
