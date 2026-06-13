"""FleetWatchdog — SRE unifié de la flotte Argos Ops (Axe 3.2, fusion D-031).

Fusionne les 4 anciens watchers qui lisaient tous la table ``agent_runs``
(``BotHealthBot`` + ``BotPerfAnalyzer`` + ``ErrorTriageBot`` +
``LogAnomalyDetector``) en **un seul agent** : 1 session DB, 4 sous-analyses
réutilisant la logique pure d'origine (cf. :mod:`argos_ops.agents._watchdog`),
**1 rapport agrégé**, **1 embed multi-sections**, **1 cron** (toutes les 6 h)
au lieu de 4 agents / 4 crons / 4 embeds.

Sections (chacune garde sa sémantique et ses seuils d'origine) :
- **Santé / Freshness** — dernier run + stale + erreurs 24 h par agent + breakers
- **Perf** — latence P50/P95 + taux d'erreur 7 j vs baseline J-14→J-7
- **Triage erreurs** — clustering par signature d'exception sur 24 h
- **Anomalie volume** — pic d'erreurs dernière heure vs baseline 24 h

Agrégation (« le plus sévère gagne », cohérent avec la convention cerveau) :
``should_alert`` = OR des 4 ; couleur = pire des 4 (RED > YELLOW > GREEN) ;
silence Discord si les 4 sections sont vertes. Politique silence-si-vert
déléguée à :func:`argos_ops.agents._watcher_base.emit_alert_or_silence`.

Cf. plan ``docs/ARGOS_OPS_PLAN.md`` Annexe D § 12 Meta-Ops et docs/DECISIONS.md.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime

from argos_ops.agents._watchdog import anomaly, errors, health, perf
from argos_ops.agents._watchdog.health import MONITORED_AGENTS
from argos_ops.agents._watcher_base import (
    WatcherReport,
    color_title,
    emit_alert_or_silence,
)
from argos_ops.agents.base import BaseAgent, IOItem, RunResult
from argos_ops.crm.db import session_scope
from argos_ops.crm.repository import list_tripped_breakers
from argos_ops.notifications.discord import (
    GREEN,
    RED,
    YELLOW,
    Embed,
    EmbedField,
)

# Limite Discord : 25 fields max par embed.
_MAX_EMBED_FIELDS = 25

# Sévérité des couleurs pour le « pire gagne ». Les 4 sections ne produisent
# que GREEN/YELLOW/RED ; tout int inconnu retombe sur 0 (traité comme vert).
_COLOR_SEVERITY: dict[int, int] = {GREEN: 0, YELLOW: 1, RED: 2}


@dataclass(frozen=True)
class FleetWatchdogReport:
    """Rapport agrégé des 4 sous-sections. Conforme au Protocol
    ``WatcherReport`` (should_alert / alert_color / summary)."""

    health: health.BotHealthReport
    perf: perf.PerfReport
    triage: errors.TriageReport
    anomaly: anomaly.AnomalyReport
    should_alert: bool
    alert_color: int
    summary: str


def _section_word(color: int) -> str:
    return color_title(color, green=GREEN, yellow=YELLOW, red=RED)


def _worst_color(*colors: int) -> int:
    """Retourne la couleur la plus sévère (RED > YELLOW > GREEN)."""
    return max(colors, key=lambda c: _COLOR_SEVERITY.get(c, 0))


def aggregate_report(
    health_report: health.BotHealthReport,
    perf_report: perf.PerfReport,
    triage_report: errors.TriageReport,
    anomaly_report: anomaly.AnomalyReport,
) -> FleetWatchdogReport:
    """Combine les 4 sous-rapports : alerte si ≥1 section alerte, couleur =
    pire des 4, summary = ligne compacte des statuts par section."""
    should_alert = (
        health_report.should_alert
        or perf_report.should_alert
        or triage_report.should_alert
        or anomaly_report.should_alert
    )
    alert_color = _worst_color(
        health_report.alert_color,
        perf_report.alert_color,
        triage_report.alert_color,
        anomaly_report.alert_color,
    )
    summary = (
        f"santé [{_section_word(health_report.alert_color)}] · "
        f"perf [{_section_word(perf_report.alert_color)}] · "
        f"erreurs [{_section_word(triage_report.alert_color)}] · "
        f"anomalie [{_section_word(anomaly_report.alert_color)}]"
    )
    return FleetWatchdogReport(
        health=health_report,
        perf=perf_report,
        triage=triage_report,
        anomaly=anomaly_report,
        should_alert=should_alert,
        alert_color=alert_color,
        summary=summary,
    )


def build_fleet_embed(report: FleetWatchdogReport, *, now: datetime | None = None) -> Embed:
    """Construit l'embed Discord unique — une section (header + fields) par
    sous-analyse **qui alerte** (les sections vertes ne sont pas dépliées :
    le statut global reste lisible dans la description). Cap à 25 fields."""
    now = now or datetime.now(UTC)

    # ``sub`` typé WatcherReport : les 4 *Report satisfont le Protocol
    # (should_alert / alert_color / summary) → pas de type: ignore.
    sections: tuple[tuple[str, WatcherReport, list[EmbedField]], ...] = (
        ("Santé / Freshness", report.health, health.health_fields(report.health)),
        ("Perf latence/erreurs", report.perf, perf.perf_fields(report.perf)),
        ("Triage erreurs", report.triage, errors.triage_fields(report.triage)),
        ("Anomalie volume", report.anomaly, anomaly.anomaly_fields(report.anomaly)),
    )

    fields: list[EmbedField] = []
    for label, sub, sub_fields in sections:
        if not sub.should_alert:
            continue
        word = _section_word(sub.alert_color)
        fields.append(
            EmbedField(
                name=f"── {label} · {word} ──",
                value=sub.summary[:1020],
                inline=False,
            )
        )
        fields.extend(sub_fields)

    if len(fields) > _MAX_EMBED_FIELDS:
        kept = fields[: _MAX_EMBED_FIELDS - 1]
        dropped = len(fields) - len(kept)
        kept.append(
            EmbedField(
                name="…",
                value=f"+{dropped} field(s) tronqué(s) (limite Discord 25)",
                inline=False,
            )
        )
        fields = kept

    title_status = _section_word(report.alert_color)
    return Embed(
        title=f"FleetWatchdog — {title_status}",
        description=report.summary,
        color=report.alert_color,
        fields=fields,
        footer="Argos Ops • FleetWatchdog",
        timestamp=now.isoformat(),
    )


def _build_io(
    health_report: health.BotHealthReport,
    perf_report: perf.PerfReport,
    triage_report: errors.TriageReport,
    anomaly_report: anomaly.AnomalyReport,
) -> tuple[list[IOItem], list[IOItem]]:
    """IN/OUT structuré pour l'onglet Travail du cockpit (union des 4 watchers)."""
    stale = [s for s in health_report.snapshots if s.status == "stale"]
    errored = [s for s in health_report.snapshots if s.status == "error"]
    regressions = [s for s in perf_report.snapshots if s.status == "regression"]
    warns = [s for s in perf_report.snapshots if s.status == "warn"]

    inputs = [
        IOItem(
            label="Agents surveillés",
            kind="db",
            detail="agent_runs (dernier run + durée 7j + erreurs 24h)",
            count=len(health_report.snapshots),
        ),
        IOItem(
            label="Circuit breakers",
            kind="db",
            detail="état tripped",
            count=len(health_report.tripped_breakers),
        ),
        IOItem(
            label="Erreurs runtime 24h",
            kind="db",
            detail="agent_runs.error sur 24h",
            count=triage_report.total_errors,
        ),
        IOItem(
            label="Erreurs dernière heure",
            kind="db",
            detail=f"baseline {anomaly_report.baseline_hourly:.1f}/h",
            count=anomaly_report.current_count,
        ),
    ]
    outputs = [
        IOItem(
            label="Agents stale",
            kind="memory",
            detail=", ".join(s.agent_name for s in stale) or None,
            count=len(stale),
        ),
        IOItem(
            label="Agents en erreur",
            kind="memory",
            detail=", ".join(s.agent_name for s in errored) or None,
            count=len(errored),
        ),
        IOItem(
            label="Breakers tripped",
            kind="memory",
            detail=", ".join(br.name for br in health_report.tripped_breakers) or None,
            count=len(health_report.tripped_breakers),
        ),
        IOItem(
            label="Régressions perf (>=2x)",
            kind="other",
            detail=", ".join(f"{s.agent_name} ({s.reason})" for s in regressions) or None,
            count=len(regressions),
        ),
        IOItem(
            label="Dérives perf (>=1.5x)",
            kind="other",
            detail=", ".join(f"{s.agent_name} ({s.reason})" for s in warns) or None,
            count=len(warns),
        ),
        IOItem(
            label=f"Clusters d'erreurs (>= {errors.MIN_OCCURRENCES_TO_ALERT})",
            kind="other",
            detail=", ".join(f"{c.signature} x{c.count}" for c in triage_report.clusters) or None,
            count=len(triage_report.clusters),
        ),
        IOItem(
            label=f"Pic d'erreurs ({anomaly_report.status})",
            kind="other",
            detail=f"ratio {anomaly_report.ratio:.1f}x vs baseline",
            count=anomaly_report.current_count,
        ),
    ]
    return inputs, outputs


class FleetWatchdog(BaseAgent):
    """SRE unifié — fusionne santé + perf + triage erreurs + anomalie en
    une seule passe sur ``agent_runs``."""

    name = "FleetWatchdog"
    command = "/run-fleet-watchdog"
    breaker_name = None  # pas de breaker dédié : c'est lui qui les observe
    ai_act_risk_class = "minimal"

    def __init__(
        self,
        *,
        agent_names: Iterable[str] | None = None,
        max_age_hours: dict[str, float] | None = None,
    ) -> None:
        self._agent_names = tuple(agent_names or MONITORED_AGENTS)
        self._max_age_hours = max_age_hours

    async def run(self) -> RunResult:
        now = datetime.now(UTC)
        async with session_scope() as session:
            # Section 1 — santé / freshness + breakers
            health_snaps = await health.collect_snapshots(
                session,
                agent_names=self._agent_names,
                max_age_hours=self._max_age_hours,
                now=now,
            )
            tripped = await list_tripped_breakers(session)
            health_report = health.build_report(health_snaps, tripped)

            # Section 2 — perf (latence P50/P95 + taux d'erreur)
            perf_snaps = await perf.collect_snapshots(
                session, agent_names=self._agent_names, now=now
            )
            perf_report = perf.build_report(perf_snaps)

            # Section 3 — triage des erreurs (clusters par signature, 24h)
            clusters, total_errors = await errors.collect_clusters(session, now=now)
            triage_report = errors.build_report(clusters, total_errors)

            # Section 4 — anomalie de volume (pic 1h vs baseline 24h)
            anomaly_report = await anomaly.collect_anomaly(session, now=now)

        report = aggregate_report(health_report, perf_report, triage_report, anomaly_report)
        inputs, outputs = _build_io(health_report, perf_report, triage_report, anomaly_report)
        return await emit_alert_or_silence(
            report,
            embed_builder=build_fleet_embed,
            agent_name=self.name,
            inputs=inputs,
            outputs=outputs,
        )


__all__ = [
    "FleetWatchdog",
    "FleetWatchdogReport",
    "aggregate_report",
    "build_fleet_embed",
]
