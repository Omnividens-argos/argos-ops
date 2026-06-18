"""``FleetWatchdogScript`` — SRE unifié de la flotte (archi v2, S8).

Reprend le watchdog legacy (BotHealth + BotPerf + ErrorTriage + LogAnomaly) mais
sur le **runlog fichier** du pôle SRE (plus la table DB ``agent_runs``). Une
passe, 4 sections, 1 constat global (couleur = la plus grave) :

1. **santé** — statut/freshness de chaque script SRE (réutilise le tableau de
   statut : rouge si échec/constat rouge/breaker, jaune si stale) ;
2. **perf** — régression de P95 par script (recent vs ancien : ≥ 2x rouge, ≥ 1,5x jaune) ;
3. **erreurs** — clusters de runs ``failed`` /24 h par signature (≥ 3 jaune, ≥ 10 rouge) ;
4. **anomalie** — pic de volume d'échecs (1 h vs base 24 h).

Les 4 fonctions de section sont **pures** (testables sans disque).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from argos_ops.poles.sre import status
from argos_ops.poles.sre.base import BaseSreScript
from argos_ops.poles.sre.report import Severity, SreReport, worst
from argos_ops.poles.sre.runlog import RunLogEntry, load_runs, percentiles
from argos_ops.poles.sre.status import ScriptStatus

# perf
PERF_MIN_SAMPLES = 5
PERF_WARN_FACTOR = 1.5
PERF_REGRESSION_FACTOR = 2.0
# erreurs
ERROR_WINDOW_HOURS = 24
ERROR_MIN_OCCURRENCES = 3
ERROR_CRITICAL_OCCURRENCES = 10
# anomalie
ANOMALY_CURRENT_HOURS = 1
ANOMALY_BASELINE_HOURS = 24
ANOMALY_ABSOLUTE_MIN = 5
ANOMALY_ABSOLUTE_CRITICAL = 50
ANOMALY_WARN_RATIO = 3.0
ANOMALY_CRITICAL_RATIO = 5.0

_SIGNATURE_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_.]*)")


@dataclass(frozen=True)
class Section:
    """Une section du watchdog."""

    name: str
    severity: Severity
    summary: str
    detail: str = ""


# =============================================================================
# 1. santé
# =============================================================================
def health_section(rows: list[ScriptStatus]) -> Section:
    n_red = sum(1 for r in rows if r.health == "red")
    n_yellow = sum(1 for r in rows if r.health == "yellow")
    n_green = len(rows) - n_red - n_yellow
    severity: Severity = worst("red" if n_red else "green", "yellow" if n_yellow else "green")
    summary = f"{n_green} sain · {n_yellow} jaune · {n_red} rouge"
    detail = "\n".join(
        f"- {r.script} : {r.health}" + (f" — {r.last_summary}" if r.last_summary else "")
        for r in rows
        if r.health != "green"
    )
    return Section("santé", severity, summary, detail)


# =============================================================================
# 2. perf (régression P95 par script)
# =============================================================================
def _script_perf_status(entries: list[RunLogEntry]) -> tuple[str, float | None]:
    """Statut perf d'un script à partir de ses runs exécutés (récents → vieux).

    Compare la P95 de la moitié récente vs la moitié ancienne. Renvoie
    ``(status, ratio)`` — status ∈ ok|warn|regression (ou ``ok`` si trop peu).
    """
    executed = [e for e in entries if e.status != "skipped"]
    if len(executed) < 2 * PERF_MIN_SAMPLES:
        return "ok", None
    ordered = sorted(executed, key=lambda e: e.at)  # vieux → récent
    half = len(ordered) // 2
    _, old_p95 = percentiles([e.duration_ms for e in ordered[:half]])
    _, new_p95 = percentiles([e.duration_ms for e in ordered[half:]])
    if not old_p95 or not new_p95 or old_p95 <= 0:
        return "ok", None
    ratio = new_p95 / old_p95
    if ratio >= PERF_REGRESSION_FACTOR:
        return "regression", ratio
    if ratio >= PERF_WARN_FACTOR:
        return "warn", ratio
    return "ok", ratio


def perf_section(runs: list[RunLogEntry]) -> Section:
    by_script: dict[str, list[RunLogEntry]] = {}
    for r in runs:
        by_script.setdefault(r.script, []).append(r)
    statuses = {s: _script_perf_status(es) for s, es in by_script.items()}
    n_regression = sum(1 for st, _ in statuses.values() if st == "regression")
    n_warn = sum(1 for st, _ in statuses.values() if st == "warn")
    severity: Severity = worst("red" if n_regression else "green", "yellow" if n_warn else "green")
    summary = f"{n_regression} régression(s) · {n_warn} ralentissement(s) (P95)"
    detail = "\n".join(
        f"- {s} : {st} (P95 x{ratio:.1f})"
        for s, (st, ratio) in sorted(statuses.items())
        if st != "ok" and ratio is not None
    )
    return Section("perf", severity, summary, detail)


# =============================================================================
# 3. erreurs (clusters de runs failed /24h)
# =============================================================================
def error_signature(error: str | None) -> str:
    if not error:
        return "<unknown>"
    m = _SIGNATURE_RE.match(error.strip())
    return m.group(1) if m else "<unknown>"


def errors_section(runs: list[RunLogEntry], *, now: datetime) -> Section:
    cutoff = now - timedelta(hours=ERROR_WINDOW_HOURS)
    failed = [r for r in runs if r.status == "failed" and r.at >= cutoff]
    clusters: dict[str, int] = {}
    for r in failed:
        sig = error_signature(r.error)
        clusters[sig] = clusters.get(sig, 0) + 1
    above = {sig: n for sig, n in clusters.items() if n >= ERROR_MIN_OCCURRENCES}
    has_critical = any(n >= ERROR_CRITICAL_OCCURRENCES for n in above.values())
    severity: Severity = worst("red" if has_critical else "green", "yellow" if above else "green")
    summary = f"{len(above)} cluster(s) ≥ {ERROR_MIN_OCCURRENCES} · {len(failed)} échec(s) /24h"
    detail = "\n".join(f"- {sig} : {n}" for sig, n in sorted(above.items(), key=lambda kv: -kv[1]))
    return Section("erreurs", severity, summary, detail)


# =============================================================================
# 4. anomalie (pic de volume d'échecs)
# =============================================================================
def anomaly_section(runs: list[RunLogEntry], *, now: datetime) -> Section:
    current_cut = now - timedelta(hours=ANOMALY_CURRENT_HOURS)
    baseline_cut = now - timedelta(hours=ANOMALY_BASELINE_HOURS + ANOMALY_CURRENT_HOURS)
    current = sum(1 for r in runs if r.status == "failed" and r.at >= current_cut)
    baseline = sum(1 for r in runs if r.status == "failed" and baseline_cut <= r.at < current_cut)
    baseline_hourly = max(baseline / ANOMALY_BASELINE_HOURS, 1.0)
    ratio = current / baseline_hourly
    if current < ANOMALY_ABSOLUTE_MIN:
        severity: Severity = "green"
    elif current >= ANOMALY_ABSOLUTE_CRITICAL or ratio >= ANOMALY_CRITICAL_RATIO:
        severity = "red"
    elif ratio >= ANOMALY_WARN_RATIO:
        severity = "yellow"
    else:
        severity = "green"
    summary = f"{current} échec(s) /1h (base {baseline_hourly:.1f}/h · x{ratio:.1f})"
    return Section("anomalie", severity, summary)


# =============================================================================
# agrégation
# =============================================================================
def aggregate(sections: list[Section]) -> SreReport:
    severity = worst(*(s.severity for s in sections))
    summary = " · ".join(f"{s.name} {s.severity}" for s in sections)
    detail = "\n\n".join(
        f"**{s.name}** ({s.severity}) — {s.summary}" + (f"\n{s.detail}" if s.detail else "")
        for s in sections
    )
    return SreReport(severity, summary, detail)


class FleetWatchdogScript(BaseSreScript):
    """SRE unifié : santé · perf · erreurs · anomalie en une passe sur le runlog."""

    name = "fleet_watchdog"

    async def check(self) -> SreReport:
        now = datetime.now(UTC)
        runs = load_runs(poles_root=self.poles_root)
        rows = status.compute_status(now=now, poles_root=self.poles_root)
        sections = [
            health_section(rows),
            perf_section(runs),
            errors_section(runs, now=now),
            anomaly_section(runs, now=now),
        ]
        return aggregate(sections)


__all__ = [
    "ERROR_CRITICAL_OCCURRENCES",
    "ERROR_MIN_OCCURRENCES",
    "PERF_REGRESSION_FACTOR",
    "PERF_WARN_FACTOR",
    "FleetWatchdogScript",
    "Section",
    "aggregate",
    "anomaly_section",
    "error_signature",
    "errors_section",
    "health_section",
    "perf_section",
]
