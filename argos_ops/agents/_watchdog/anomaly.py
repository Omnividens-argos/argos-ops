"""Section *anomalie de volume* du FleetWatchdog (ex-``LogAnomalyDetector``, Axe 3.2).

Détecte les **pics** d'erreurs dans ``agent_runs`` (les logs Loguru des
agents sont déjà persistés là par ``run_agent()``). Complémentaire de la
section triage :

- la section triage répond à *"quelles erreurs reviennent souvent ?"*
  (clusters par signature, seuil ≥3 occurrences/24 h)
- cette section répond à *"sommes-nous dans une dérive anormale ?"*
  (volume d'erreurs sur la dernière heure vs baseline)

Politique de couleur (agrégée par FleetWatchdog) :
- **vert**  si volume horaire < :data:`SPIKE_ABSOLUTE_MIN` (bruit de fond)
  **et** ratio current/baseline < :data:`SPIKE_WARN_RATIO`
- **jaune** si current ≥ :data:`SPIKE_WARN_RATIO` x baseline
- **rouge** si current ≥ :data:`SPIKE_CRITICAL_RATIO` x baseline ou
  current ≥ :data:`SPIKE_ABSOLUTE_CRITICAL`

Le baseline = nombre moyen d'erreurs par heure sur les
:data:`BASELINE_HOURS` heures précédant la dernière heure (avec un
plancher :data:`BASELINE_FLOOR` pour éviter qu'un baseline à 0 ne fasse
exploser le ratio).

Cf. plan ``docs/ARGOS_OPS_PLAN.md`` Annexe D § 7 Tech/SRE.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col

from argos_ops.agents._watcher_base import color_title
from argos_ops.crm.models import AgentRun
from argos_ops.notifications.discord import GREEN, RED, YELLOW, Embed, EmbedField

AnomalyStatus = Literal["normal", "spike_warn", "spike_critical"]

CURRENT_WINDOW_HOURS = 1
BASELINE_HOURS = 24
BASELINE_FLOOR = 1.0  # évite ratio = current/0
SPIKE_WARN_RATIO = 3.0
SPIKE_CRITICAL_RATIO = 5.0
SPIKE_ABSOLUTE_MIN = 5  # en-dessous, on ne déclenche jamais
SPIKE_ABSOLUTE_CRITICAL = 50  # même si ratio modeste, c'est un volume critique


@dataclass(frozen=True)
class AnomalyReport:
    """Résultat agrégé de la section anomalie de volume."""

    current_count: int
    baseline_hourly: float
    ratio: float
    top_agents: list[tuple[str, int]]  # (agent_name, count) sur la fenêtre courante
    status: AnomalyStatus
    should_alert: bool
    alert_color: int
    summary: str


async def _count_errors_in_window(
    session: AsyncSession, *, since: datetime, until: datetime
) -> int:
    """COUNT(*) sur ``agent_runs`` où ``error IS NOT NULL`` dans la fenêtre."""
    stmt = (
        select(func.count())
        .select_from(AgentRun)
        .where(col(AgentRun.started_at) >= since)
        .where(col(AgentRun.started_at) < until)
        .where(col(AgentRun.error).is_not(None))
    )
    return int((await session.execute(stmt)).scalar_one())


async def _top_agents_in_window(
    session: AsyncSession, *, since: datetime, until: datetime, limit: int = 5
) -> list[tuple[str, int]]:
    """Top N agents par nombre d'erreurs dans la fenêtre courante."""
    stmt = (
        select(col(AgentRun.agent_name), func.count().label("n"))
        .where(col(AgentRun.started_at) >= since)
        .where(col(AgentRun.started_at) < until)
        .where(col(AgentRun.error).is_not(None))
        .group_by(col(AgentRun.agent_name))
        .order_by(func.count().desc())
        .limit(limit)
    )
    rows = (await session.execute(stmt)).all()
    return [(str(name), int(n)) for name, n in rows]


def classify(current_count: int, baseline_hourly: float) -> AnomalyStatus:
    """Décide ``normal`` / ``spike_warn`` / ``spike_critical``.

    Un volume sous :data:`SPIKE_ABSOLUTE_MIN` ne déclenche jamais
    (bruit de fond). Au-dessus, on regarde le ratio vs baseline ET le
    seuil absolu critique.
    """
    if current_count < SPIKE_ABSOLUTE_MIN:
        return "normal"
    floor = max(baseline_hourly, BASELINE_FLOOR)
    ratio = current_count / floor
    if current_count >= SPIKE_ABSOLUTE_CRITICAL or ratio >= SPIKE_CRITICAL_RATIO:
        return "spike_critical"
    if ratio >= SPIKE_WARN_RATIO:
        return "spike_warn"
    return "normal"


def build_report(
    current_count: int,
    baseline_hourly: float,
    top_agents: list[tuple[str, int]],
) -> AnomalyReport:
    """Construit le report final avec couleur + ratio + summary canonique."""
    status = classify(current_count, baseline_hourly)
    floor = max(baseline_hourly, BASELINE_FLOOR)
    ratio = current_count / floor

    if status == "spike_critical":
        alert_color = RED
    elif status == "spike_warn":
        alert_color = YELLOW
    else:
        alert_color = GREEN

    summary = f"{current_count} erreurs/1h · baseline {baseline_hourly:.1f}/h · ratio {ratio:.1f}x"

    return AnomalyReport(
        current_count=current_count,
        baseline_hourly=baseline_hourly,
        ratio=ratio,
        top_agents=top_agents,
        status=status,
        should_alert=status != "normal",
        alert_color=alert_color,
        summary=summary,
    )


async def collect_anomaly(session: AsyncSession, *, now: datetime | None = None) -> AnomalyReport:
    """Orchestration DB de la section anomalie : compte les erreurs de la
    dernière heure vs baseline 24 h et construit le report.

    Extrait du ``run()`` de l'ancien ``LogAnomalyDetector`` pour que
    FleetWatchdog l'appelle en une ligne sur la session partagée.
    """
    now = now or datetime.now(UTC)
    current_start = now - timedelta(hours=CURRENT_WINDOW_HOURS)
    baseline_start = now - timedelta(hours=CURRENT_WINDOW_HOURS + BASELINE_HOURS)

    current_count = await _count_errors_in_window(session, since=current_start, until=now)
    baseline_count = await _count_errors_in_window(
        session, since=baseline_start, until=current_start
    )
    top_agents = await _top_agents_in_window(session, since=current_start, until=now)

    baseline_hourly = baseline_count / BASELINE_HOURS
    return build_report(current_count, baseline_hourly, top_agents)


def anomaly_fields(report: AnomalyReport) -> list[EmbedField]:
    """Champs Discord de la section anomalie — un field récap + un field par
    top agent. Réutilisé par l'embed combiné FleetWatchdog."""
    fields: list[EmbedField] = [
        EmbedField(
            name="Volume",
            value=(
                f"`{report.current_count}` erreurs sur la dernière heure\n"
                f"baseline {report.baseline_hourly:.1f}/h · "
                f"ratio **{report.ratio:.1f}x**"
            ),
            inline=False,
        )
    ]
    if report.top_agents:
        fields.append(
            EmbedField(
                name="Top agents",
                value="\n".join(f"`{name}` — {n}" for name, n in report.top_agents),
                inline=False,
            )
        )
    return fields


def build_anomaly_embed(report: AnomalyReport, *, now: datetime | None = None) -> Embed:
    """Construit l'embed Discord autonome de la section anomalie."""
    now = now or datetime.now(UTC)
    title_status = color_title(report.alert_color, green=GREEN, yellow=YELLOW, red=RED)
    return Embed(
        title=f"LogAnomalyDetector — {title_status}",
        description=report.summary,
        color=report.alert_color,
        fields=anomaly_fields(report),
        footer="Argos Ops • LogAnomalyDetector",
        timestamp=now.isoformat(),
    )


__all__ = [
    "BASELINE_FLOOR",
    "BASELINE_HOURS",
    "CURRENT_WINDOW_HOURS",
    "SPIKE_ABSOLUTE_CRITICAL",
    "SPIKE_ABSOLUTE_MIN",
    "SPIKE_CRITICAL_RATIO",
    "SPIKE_WARN_RATIO",
    "AnomalyReport",
    "AnomalyStatus",
    "anomaly_fields",
    "build_anomaly_embed",
    "build_report",
    "classify",
    "collect_anomaly",
]
