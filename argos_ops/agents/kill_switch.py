"""KillSwitchOperator — Safety Officer de la flotte (P22.C Meta-Ops Sprint 2).

Surveille les circuit breakers (P15) qui restent tripped trop longtemps
sans intervention humaine. Pour chaque breaker tripped depuis plus de
:data:`MIN_STALE_HOURS` (4h par défaut), pousse un rappel Discord
**dédoublonné 1x/jour** : on ne re-spamme pas le même breaker tant
qu'on a déjà alerté dans les 24 dernières heures.

La déduplication s'appuie sur ``agent_runs`` : on inspecte les
``output_summary`` de KillSwitchOperator sur 24 h pour vérifier si
chaque breaker a déjà été mentionné.

L'embed inclut un **guide de reset** (commande ``/reset-breaker <name>``)
pour minimiser la friction humaine.

Cet agent **n'a pas de slash command** — il tourne via Task Scheduler
(``argos-ops-kill-switch``, cron 0 9,17 * * *, donc 2x/jour).

Cf. plan ``docs/ARGOS_OPS_PLAN.md`` Annexe D § 12 Meta-Ops, Sprint 2.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col

from argos_ops.agents._watcher_base import color_title, emit_alert_or_silence, format_age
from argos_ops.agents.base import BaseAgent, IOItem, RunResult
from argos_ops.crm.db import session_scope
from argos_ops.crm.models import AgentRun, Breaker
from argos_ops.crm.repository import list_tripped_breakers
from argos_ops.notifications.discord import GREEN, RED, YELLOW, Embed, EmbedField

MIN_STALE_HOURS = 4.0
CRITICAL_STALE_HOURS = 24.0
DEDUP_WINDOW_HOURS = 24


@dataclass(frozen=True)
class StaleBreaker:
    """Breaker tripped depuis trop longtemps, candidat à l'alerte."""

    name: str
    age_hours: float
    reason: str | None
    already_alerted_recently: bool


@dataclass(frozen=True)
class KillSwitchReport:
    """Résultat agrégé du run KillSwitchOperator."""

    candidates: list[StaleBreaker]
    to_alert: list[StaleBreaker]  # sous-ensemble : ceux non encore alertés
    should_alert: bool
    alert_color: int
    summary: str


# =============================================================================
# Lecture + dédoublonnage
# =============================================================================
def _breaker_age_hours(breaker: Breaker, *, now: datetime) -> float | None:
    if breaker.tripped_at is None:
        return None
    ts = breaker.tripped_at
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=UTC)
    return (now - ts).total_seconds() / 3600.0


async def _recent_alerted_breakers(
    session: AsyncSession,
    *,
    since: datetime,
) -> set[str]:
    """Liste les noms de breakers déjà mentionnés dans un run récent.

    Lecture des ``agent_runs`` du KillSwitchOperator sur 24 h dont
    ``output_summary`` contient ``"alert pushed"`` — le nom du breaker
    est stocké dans ``extras["alerted_breakers"]`` mais on n'a pas accès
    direct au JSON depuis SQL portable, donc on stocke aussi les noms en
    clair dans ``output_summary`` (format ``"alert pushed — N breakers:
    name1,name2"``) pour rester lisible et parsable.
    """
    stmt = (
        select(AgentRun)
        .where(col(AgentRun.agent_name) == "KillSwitchOperator")
        .where(col(AgentRun.started_at) >= since)
        .where(col(AgentRun.output_summary).like("alert pushed%"))
    )
    runs = list((await session.execute(stmt)).scalars().all())
    already: set[str] = set()
    for run in runs:
        summary = run.output_summary or ""
        if "breakers:" not in summary:
            continue
        _, _, listing = summary.partition("breakers:")
        for name in listing.split(","):
            already.add(name.strip())
    return already


async def collect_candidates(
    session: AsyncSession,
    *,
    now: datetime | None = None,
    min_stale_hours: float = MIN_STALE_HOURS,
) -> list[StaleBreaker]:
    """Liste les breakers tripped depuis > seuil + flag dédoublonnage."""
    now = now or datetime.now(UTC)
    tripped = await list_tripped_breakers(session)
    dedup_since = now - timedelta(hours=DEDUP_WINDOW_HOURS)
    already = await _recent_alerted_breakers(session, since=dedup_since)

    out: list[StaleBreaker] = []
    for breaker in tripped:
        age = _breaker_age_hours(breaker, now=now)
        if age is None or age < min_stale_hours:
            continue
        out.append(
            StaleBreaker(
                name=breaker.name,
                age_hours=round(age, 2),
                reason=breaker.reason,
                already_alerted_recently=breaker.name in already,
            )
        )
    out.sort(key=lambda b: b.age_hours, reverse=True)
    return out


# =============================================================================
# Décision d'alerte
# =============================================================================
def build_report(
    candidates: list[StaleBreaker],
    *,
    critical_stale_hours: float = CRITICAL_STALE_HOURS,
) -> KillSwitchReport:
    """Filtre les candidats déjà alertés et calcule la couleur."""
    to_alert = [b for b in candidates if not b.already_alerted_recently]
    has_critical = any(b.age_hours >= critical_stale_hours for b in to_alert)
    should_alert = bool(to_alert)

    if has_critical:
        alert_color = RED
    elif should_alert:
        alert_color = YELLOW
    else:
        alert_color = GREEN

    suppressed = len(candidates) - len(to_alert)
    parts = [
        f"{len(to_alert)} breaker(s) stale >= {MIN_STALE_HOURS}h",
    ]
    if suppressed:
        parts.append(f"{suppressed} suppressed (déjà alerté ces {DEDUP_WINDOW_HOURS}h)")
    if to_alert:
        names = ",".join(b.name for b in to_alert)
        parts.append(f"breakers:{names}")
    summary = " · ".join(parts)

    return KillSwitchReport(
        candidates=candidates,
        to_alert=to_alert,
        should_alert=should_alert,
        alert_color=alert_color,
        summary=summary,
    )


# =============================================================================
# Formatting
# =============================================================================
def _format_breaker_value(breaker: StaleBreaker) -> str:
    reason = breaker.reason or "<no reason>"
    return (
        f"tripped {format_age(breaker.age_hours)} ago\n"
        f"reason: `{reason[:200]}`\n"
        f"reset: `/reset-breaker {breaker.name}`"
    )


def build_kill_switch_embed(report: KillSwitchReport, *, now: datetime | None = None) -> Embed:
    """Construit l'embed Discord — un field par breaker à alerter."""
    now = now or datetime.now(UTC)
    fields = [
        EmbedField(
            name=f"[STALE] {breaker.name}",
            value=_format_breaker_value(breaker),
            inline=False,
        )
        for breaker in report.to_alert
    ]
    title_status = color_title(report.alert_color, green=GREEN, yellow=YELLOW, red=RED)
    return Embed(
        title=f"KillSwitchOperator — {title_status}",
        description=report.summary,
        color=report.alert_color,
        fields=fields,
        footer="Argos Ops • KillSwitchOperator",
        timestamp=now.isoformat(),
    )


# =============================================================================
# Agent
# =============================================================================
class KillSwitchOperator(BaseAgent):
    """Safety Officer — alerte 1x/jour pour breakers stale, guide le reset."""

    name = "KillSwitchOperator"
    command = None  # pas de slash command
    breaker_name = None
    ai_act_risk_class = "minimal"

    async def run(self) -> RunResult:
        async with session_scope() as session:
            candidates = await collect_candidates(session)
        report = build_report(candidates)
        inputs = [
            IOItem(
                label="Circuit breakers tripped",
                kind="db",
                detail=f"breakers stale >= {MIN_STALE_HOURS}h",
                count=len(candidates),
            ),
            IOItem(
                label="Historique alertes KillSwitch",
                kind="db",
                detail=f"agent_runs (dédup {DEDUP_WINDOW_HOURS}h)",
            ),
        ]
        outputs = [
            IOItem(
                label="Breakers à relancer (rappel reset)",
                kind="other",
                detail=", ".join(b.name for b in report.to_alert) or None,
                count=len(report.to_alert),
            ),
        ]
        return await emit_alert_or_silence(
            report,
            embed_builder=build_kill_switch_embed,
            agent_name=self.name,
            inputs=inputs,
            outputs=outputs,
        )


__all__ = [
    "CRITICAL_STALE_HOURS",
    "DEDUP_WINDOW_HOURS",
    "MIN_STALE_HOURS",
    "KillSwitchOperator",
    "KillSwitchReport",
    "StaleBreaker",
    "build_kill_switch_embed",
    "build_report",
    "collect_candidates",
]
