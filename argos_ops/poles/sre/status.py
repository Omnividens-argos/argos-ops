"""Tableau de **statut temps réel** des scripts SRE (archi v2, S8).

Agrège, pour chaque script déclaré dans ``data/poles/sre/pole.yaml``, l'état que
le cockpit affiche en vert / jaune / rouge :

- dernier run (statut + sévérité du constat) depuis le runlog ;
- freshness : âge du dernier run et passages cron **manqués** (stale si ≥ 2) ;
- perfs P50/P95 (ms) ;
- gel kill-switch et breaker éponyme armé.

``health`` est la couleur consolidée d'une ligne : rouge si run en échec /
constat rouge / breaker armé ; jaune si constat jaune ou stale ; vert sinon. Le
gel kill-switch est un état **intentionnel** (badge séparé) qui n'aggrave pas la
santé. Pur calcul de lecture, local-first.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from argos_ops.poles.config import POLES_DIR, load_pole_config
from argos_ops.poles.sre import breakers, schedule
from argos_ops.poles.sre.killswitch import load_killswitch
from argos_ops.poles.sre.report import Severity, worst
from argos_ops.poles.sre.runlog import RunLogEntry, latest_per_script, script_percentiles

SRE_POLE = "sre"
# Nombre de passages cron manqués à partir duquel un script est « stale ».
STALE_MISSED_TICKS = 2


def _utcnow() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True)
class ScriptStatus:
    """Statut consolidé d'un script SRE pour le cockpit."""

    script: str
    description: str
    schedule: str | None
    health: Severity
    last_status: str | None  # success | failed | skipped
    last_severity: Severity | None
    last_summary: str | None
    last_run_at: datetime | None
    age_hours: float | None
    next_run_at: datetime | None
    due: bool
    stale: bool
    frozen: bool
    breaker_tripped: bool
    p50_ms: float | None
    p95_ms: float | None
    n_runs: int


def _age_hours(at: datetime | None, *, now: datetime) -> float | None:
    if at is None:
        return None
    return (now - at).total_seconds() / 3600.0


def _row_health(
    *,
    last: RunLogEntry | None,
    stale: bool,
    breaker_tripped: bool,
) -> Severity:
    severities: list[Severity] = []
    if last is not None and last.status == "failed":
        severities.append("red")
    if last is not None and last.status == "success":
        severities.append(last.severity)
    if breaker_tripped:
        severities.append("red")
    if stale:
        severities.append("yellow")
    return worst(*severities) if severities else "green"


def compute_status(
    *, now: datetime | None = None, poles_root: Path = POLES_DIR
) -> list[ScriptStatus]:
    """Statut de chaque script du pôle SRE (ordre = déclaration ``pole.yaml``)."""
    moment = now or _utcnow()
    config = load_pole_config(SRE_POLE, poles_root=poles_root)
    latest = latest_per_script(poles_root=poles_root)
    ks = load_killswitch(poles_root=poles_root)
    tripped_names = {b.name for b in breakers.list_tripped(poles_root=poles_root)}

    rows: list[ScriptStatus] = []
    for spec in config.scripts:
        last = latest.get(spec.id)
        last_run_at = last.at if last else None
        due = (
            schedule.is_due(spec.schedule, last_run=last_run_at, now=moment)
            if spec.schedule
            else False
        )
        missed = (
            schedule.missed_ticks(spec.schedule, last_run=last_run_at, now=moment)
            if spec.schedule and last_run_at
            else 0
        )
        stale = missed >= STALE_MISSED_TICKS
        breaker_tripped = spec.id in tripped_names
        p50, p95, n_runs = script_percentiles(spec.id, poles_root=poles_root)
        rows.append(
            ScriptStatus(
                script=spec.id,
                description=spec.description,
                schedule=spec.schedule,
                health=_row_health(last=last, stale=stale, breaker_tripped=breaker_tripped),
                last_status=last.status if last else None,
                last_severity=last.severity if last else None,
                last_summary=last.summary if last else None,
                last_run_at=last_run_at,
                age_hours=_age_hours(last_run_at, now=moment),
                next_run_at=(
                    schedule.next_run(spec.schedule, after=last_run_at or moment)
                    if spec.schedule
                    else None
                ),
                due=due,
                stale=stale,
                frozen=ks.is_frozen(spec.id),
                breaker_tripped=breaker_tripped,
                p50_ms=p50,
                p95_ms=p95,
                n_runs=n_runs,
            )
        )
    return rows


def fleet_health(rows: list[ScriptStatus]) -> Severity:
    """Couleur globale du pôle = la plus grave parmi les lignes."""
    return worst(*(r.health for r in rows)) if rows else "green"


__all__ = [
    "STALE_MISSED_TICKS",
    "ScriptStatus",
    "compute_status",
    "fleet_health",
]
