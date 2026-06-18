"""Cadence cron de la flotte (archi v2, S8).

Source unique de la cadence : le champ ``schedule`` (cron 5 champs) de chaque
``ScriptSpec`` déclaré dans les ``pole.yaml`` (cf. :mod:`argos_ops.poles.config`).
Ce module enrobe :mod:`croniter` pour répondre à 3 questions déterministes :

- un script est-il **dû** maintenant (``is_due``) au vu de son dernier run ?
- quand est son **prochain** passage (``next_run``) ?
- combien de passages a-t-il **manqués** depuis son dernier run (``missed_ticks``)
  — base du flag « stale » du tableau de statut.

Réutilisé par l'orchestrateur (décision launch/skip) et par le cockpit (planning
cron, freshness). 100 % local, aucune horloge externe.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from croniter import croniter
from loguru import logger

from argos_ops.poles.config import POLES_DIR, load_all_poles

# Garde-fou anti-boucle : un cron pathologique (ex. toutes les minutes depuis un
# last_run très ancien) ne doit pas faire tourner ``missed_ticks`` à l'infini.
_MAX_TICKS_SCAN = 10_000


def _utcnow() -> datetime:
    return datetime.now(UTC)


def is_valid_cron(expr: str | None) -> bool:
    """``True`` si ``expr`` est une expression cron 5 champs valide."""
    if not expr:
        return False
    return bool(croniter.is_valid(expr))


def next_run(expr: str, *, after: datetime) -> datetime | None:
    """Prochain passage strictement après ``after`` (``None`` si cron invalide)."""
    if not is_valid_cron(expr):
        return None
    base = after if after.tzinfo else after.replace(tzinfo=UTC)
    nxt: datetime = croniter(expr, base).get_next(datetime)
    return nxt if nxt.tzinfo else nxt.replace(tzinfo=UTC)


def prev_run(expr: str, *, before: datetime) -> datetime | None:
    """Dernier passage théorique avant ``before`` (``None`` si cron invalide)."""
    if not is_valid_cron(expr):
        return None
    base = before if before.tzinfo else before.replace(tzinfo=UTC)
    prv: datetime = croniter(expr, base).get_prev(datetime)
    return prv if prv.tzinfo else prv.replace(tzinfo=UTC)


def is_due(expr: str, *, last_run: datetime | None, now: datetime | None = None) -> bool:
    """Le script est-il dû ? ``True`` si jamais lancé, ou si un tick est passé depuis."""
    if not is_valid_cron(expr):
        return False
    moment = now or _utcnow()
    if last_run is None:
        return True
    nxt = next_run(expr, after=last_run)
    return nxt is not None and nxt <= moment


def missed_ticks(expr: str, *, last_run: datetime, now: datetime | None = None) -> int:
    """Nombre de passages cron prévus dans ``]last_run, now]`` (cappé)."""
    if not is_valid_cron(expr):
        return 0
    moment = now or _utcnow()
    base = last_run if last_run.tzinfo else last_run.replace(tzinfo=UTC)
    itr = croniter(expr, base)
    count = 0
    while count < _MAX_TICKS_SCAN:
        nxt = itr.get_next(datetime)
        if nxt.tzinfo is None:
            nxt = nxt.replace(tzinfo=UTC)
        if nxt > moment:
            break
        count += 1
    if count >= _MAX_TICKS_SCAN:
        logger.warning(f"sre.schedule : missed_ticks cappé à {_MAX_TICKS_SCAN} pour '{expr}'")
    return count


@dataclass(frozen=True)
class ScheduleEntry:
    """Cadence d'un script de la flotte, projetée à un instant donné."""

    pole: str
    script: str
    schedule: str | None
    description: str
    last_run_at: datetime | None
    next_run_at: datetime | None
    due: bool
    missed: int


def fleet_schedule(
    *,
    last_runs: dict[str, datetime] | None = None,
    now: datetime | None = None,
    poles_root: Path = POLES_DIR,
) -> list[ScheduleEntry]:
    """Calendrier cron de **tous** les scripts déclarés (avec un ``schedule``).

    ``last_runs`` mappe ``"<pole>/<script>"`` → dernier run connu (le pôle SRE le
    fournit depuis son runlog ; ailleurs ``None``). Tri : dûs d'abord, puis par
    prochain passage croissant.
    """
    moment = now or _utcnow()
    last = last_runs or {}
    out: list[ScheduleEntry] = []
    for cfg in load_all_poles(poles_root=poles_root):
        for spec in cfg.scripts:
            if not spec.schedule:
                continue
            key = f"{cfg.id}/{spec.id}"
            last_run = last.get(key)
            out.append(
                ScheduleEntry(
                    pole=cfg.id,
                    script=spec.id,
                    schedule=spec.schedule,
                    description=spec.description,
                    last_run_at=last_run,
                    next_run_at=next_run(spec.schedule, after=last_run or moment),
                    due=is_due(spec.schedule, last_run=last_run, now=moment),
                    missed=(
                        missed_ticks(spec.schedule, last_run=last_run, now=moment)
                        if last_run
                        else 0
                    ),
                )
            )
    # Dûs en tête, puis prochain passage le plus proche.
    out.sort(
        key=lambda e: (
            not e.due,
            e.next_run_at or datetime.max.replace(tzinfo=UTC),
            e.pole,
            e.script,
        )
    )
    return out


__all__ = [
    "ScheduleEntry",
    "fleet_schedule",
    "is_due",
    "is_valid_cron",
    "missed_ticks",
    "next_run",
    "prev_run",
]
