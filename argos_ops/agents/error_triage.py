"""ErrorTriageBot — Bot Ops de la flotte (P22.C Meta-Ops Sprint 2).

Lit ``agent_runs`` sur les dernières 24 h, regroupe par **signature
d'erreur** (type d'exception + premier mot du message) et alerte
Discord si ≥ :data:`MIN_OCCURRENCES_TO_ALERT` (3 par défaut) pour une
même signature.

Une signature = clé canonique extraite de ``agent_runs.error`` au
format typique ``"ConnectionError: connection refused on host..."``.
On garde ``"ConnectionError"`` comme signature primaire, et un échantillon
du message pour donner du contexte dans l'embed.

Politique anti-spam :
- **Silence** si aucune signature ne dépasse le seuil
- **Embed jaune** si ≥1 signature à 3-9 occurrences
- **Embed rouge** si ≥1 signature à ≥10 occurrences (= crise probable)

Cf. plan ``docs/ARGOS_OPS_PLAN.md`` Annexe D § 12 Meta-Ops, Sprint 2.
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col

from argos_ops.agents._watcher_base import color_title, emit_alert_or_silence
from argos_ops.agents.base import BaseAgent, RunResult
from argos_ops.crm.db import session_scope
from argos_ops.crm.models import AgentRun
from argos_ops.notifications.discord import (
    GREEN,
    RED,
    YELLOW,
    Embed,
    EmbedField,
)

TriageSeverity = Literal["info", "warn", "critical"]

WINDOW_HOURS = 24
MIN_OCCURRENCES_TO_ALERT = 3
CRITICAL_OCCURRENCES = 10
SIGNATURE_SAMPLE_MAX = 120

# Format ``error`` produit par run_agent : "ExcType: message". On extrait
# le ExcType comme signature canonique pour grouper.
_SIGNATURE_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*)")


@dataclass(frozen=True)
class ErrorCluster:
    """Groupe d'erreurs partageant la même signature."""

    signature: str
    count: int
    affected_agents: list[str]  # noms uniques des agents touchés
    sample_message: str  # premier message rencontré, tronqué


@dataclass(frozen=True)
class TriageReport:
    """Résultat agrégé du run ErrorTriageBot."""

    clusters: list[ErrorCluster]
    total_errors: int
    should_alert: bool
    alert_color: int
    summary: str = field(compare=False)


# =============================================================================
# Extraction de signature + clustering
# =============================================================================
def extract_signature(error_message: str | None) -> str:
    """Extrait la signature canonique d'un ``error`` ``agent_runs``.

    ``"ConnectionError: connection refused"`` → ``"ConnectionError"``
    ``"failed: timeout"`` → ``"failed"`` (mots simples acceptés)
    ``""`` ou ``None`` → ``"<unknown>"``
    """
    if not error_message:
        return "<unknown>"
    match = _SIGNATURE_RE.match(error_message.strip())
    if not match:
        return "<unknown>"
    return match.group(1)


async def _fetch_errors(
    session: AsyncSession, *, since: datetime
) -> list[tuple[str, str, str]]:
    """Retourne ``[(agent_name, error_message, status), ...]`` depuis ``since``."""
    stmt = (
        select(AgentRun)
        .where(col(AgentRun.started_at) >= since)
        .where(col(AgentRun.error).is_not(None))
    )
    runs = list((await session.execute(stmt)).scalars().all())
    return [(r.agent_name, r.error or "", r.status or "") for r in runs]


async def collect_clusters(
    session: AsyncSession,
    *,
    now: datetime | None = None,
    window_hours: int = WINDOW_HOURS,
) -> tuple[list[ErrorCluster], int]:
    """Construit la liste des clusters triés par count décroissant.

    Retourne aussi le total d'erreurs vues sur la fenêtre (utile pour
    le summary, indépendamment du seuil d'alerte).
    """
    now = now or datetime.now(UTC)
    since = now - timedelta(hours=window_hours)
    rows = await _fetch_errors(session, since=since)

    counts: Counter[str] = Counter()
    agents_per_sig: dict[str, set[str]] = defaultdict(set)
    samples: dict[str, str] = {}

    for agent_name, error_message, _status in rows:
        sig = extract_signature(error_message)
        counts[sig] += 1
        agents_per_sig[sig].add(agent_name)
        if sig not in samples:
            samples[sig] = error_message[:SIGNATURE_SAMPLE_MAX]

    clusters = [
        ErrorCluster(
            signature=sig,
            count=cnt,
            affected_agents=sorted(agents_per_sig[sig]),
            sample_message=samples[sig],
        )
        for sig, cnt in counts.most_common()
    ]
    return clusters, len(rows)


# =============================================================================
# Décision d'alerte
# =============================================================================
def build_report(
    clusters: list[ErrorCluster],
    total_errors: int,
    *,
    min_occurrences: int = MIN_OCCURRENCES_TO_ALERT,
    critical_occurrences: int = CRITICAL_OCCURRENCES,
) -> TriageReport:
    """Décide d'alerter selon le pire cluster.

    Filtre les clusters au-dessus du seuil et ne les affiche que ceux-là
    dans l'embed (les clusters à 1-2 occurrences sont du bruit).
    """
    above = [c for c in clusters if c.count >= min_occurrences]
    has_critical = any(c.count >= critical_occurrences for c in above)
    should_alert = bool(above)

    if has_critical:
        alert_color = RED
    elif should_alert:
        alert_color = YELLOW
    else:
        alert_color = GREEN

    summary = (
        f"{len(above)} cluster(s) >= {min_occurrences}"
        f" · {total_errors} erreur(s) totale(s) sur {WINDOW_HOURS}h"
    )
    return TriageReport(
        clusters=above,
        total_errors=total_errors,
        should_alert=should_alert,
        alert_color=alert_color,
        summary=summary,
    )


# =============================================================================
# Formatting
# =============================================================================
def _format_cluster_value(cluster: ErrorCluster) -> str:
    agents = ", ".join(cluster.affected_agents) or "<no-agent>"
    sample = cluster.sample_message or "<empty>"
    return f"x{cluster.count} · agents: {agents}\n`{sample}`"


def build_triage_embed(report: TriageReport, *, now: datetime | None = None) -> Embed:
    """Construit l'embed Discord — un field par cluster au-dessus du seuil."""
    now = now or datetime.now(UTC)
    fields = [
        EmbedField(
            name=f"[{cluster.count}] {cluster.signature}",
            value=_format_cluster_value(cluster)[:1020],
            inline=False,
        )
        for cluster in report.clusters
    ]
    title_status = color_title(report.alert_color, green=GREEN, yellow=YELLOW, red=RED)
    return Embed(
        title=f"ErrorTriageBot — {title_status}",
        description=report.summary,
        color=report.alert_color,
        fields=fields,
        footer="Argos Ops • ErrorTriageBot",
        timestamp=now.isoformat(),
    )


# =============================================================================
# Agent
# =============================================================================
class ErrorTriageBot(BaseAgent):
    """Bot Ops — trie les erreurs runtime, alerte si rafale."""

    name = "ErrorTriageBot"
    command = "/run-error-triage"
    breaker_name = None
    ai_act_risk_class = "minimal"

    async def run(self) -> RunResult:
        async with session_scope() as session:
            clusters, total = await collect_clusters(session)
        report = build_report(clusters, total)
        return await emit_alert_or_silence(
            report, embed_builder=build_triage_embed, agent_name=self.name
        )


__all__ = [
    "CRITICAL_OCCURRENCES",
    "MIN_OCCURRENCES_TO_ALERT",
    "WINDOW_HOURS",
    "ErrorCluster",
    "ErrorTriageBot",
    "TriageReport",
    "TriageSeverity",
    "build_report",
    "build_triage_embed",
    "collect_clusters",
    "extract_signature",
]
