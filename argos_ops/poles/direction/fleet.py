"""Snapshot consolidé de la flotte — cœur du pôle Direction (archi v2, S6).

Le pôle Direction est **transversal** : il lit la mémoire de **tous** les autres
pôles et en dérive une vue d'ensemble déterministe. Ce module est l'engine
réutilisé par :mod:`~argos_ops.poles.direction.digest` (digests hebdo/quotidien),
:mod:`~argos_ops.poles.direction.board` (section opérations du board pack),
:mod:`~argos_ops.poles.direction.synthesis` (synthèse de la semaine),
:mod:`~argos_ops.poles.direction.release` (garde-fou) et l'API cockpit.

Pour chaque pôle il calcule : nombre de faits, faits ``important``, faits
critiques / d'alerte, dernière activité, et une **bande de santé** dérivée
(``critical`` / ``warning`` / ``healthy`` / ``idle``). 100 % fichiers — ne dépend
que du socle (:mod:`argos_ops.poles.memory` + :mod:`argos_ops.poles.config`),
donc le pôle reste autonome (aucune dépendance de code vers un autre pôle).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from argos_ops.exceptions import ConfigError
from argos_ops.poles.config import POLES_DIR, list_poles, load_pole_config
from argos_ops.poles.memory import MemoryRecord, read_pole_memory

DIRECTION_POLE = "direction"

Health = str  # "healthy" | "warning" | "critical" | "idle"

_HEADLINE_CHARS = 130

# Un fait est « critique » si son kind ou l'un de ses tags porte l'un de ces
# marqueurs (alignés sur les sévérités des autres pôles : breaker, gel Bloctel,
# gap conformité, P0, SLA breach, churn urgent, runway sous seuil…).
_CRITICAL_MARKERS: frozenset[str] = frozenset(
    {
        "critical",
        "p0",
        "prohibited",
        "gap",
        "missed",
        "expired",
        "breach",
        "sla_breach",
        "tripped",
        "frozen",
    }
)
_WARNING_MARKERS: frozenset[str] = frozenset(
    {
        "warning",
        "warn",
        "urgent",
        "at_risk",
        "unclassified",
        "stale",
        "p1",
        "alert",
    }
)


def fact_severity(record: MemoryRecord) -> str:
    """Sévérité d'un fait mémoire : ``critical`` / ``warning`` / ``info``.

    Un fait ``important`` qui porte un marqueur critique est critique ; un fait
    ``important`` sans marqueur reste au moins ``warning`` (l'agent Mémoire ne
    protège que ce qui compte).
    """
    markers = {record.kind.lower(), *(t.lower() for t in record.tags)}
    if markers & _CRITICAL_MARKERS:
        return "critical"
    if markers & _WARNING_MARKERS:
        return "warning"
    if record.important:
        return "warning"
    return "info"


@dataclass(frozen=True)
class PoleHealth:
    """Santé synthétique d'un pôle, dérivée de sa mémoire."""

    pole: str
    name: str
    n_facts: int
    n_important: int
    n_critical: int
    n_warning: int
    last_activity: datetime | None
    health: Health
    headline: str | None
    scripts: tuple[str, ...]


@dataclass(frozen=True)
class FleetSnapshot:
    """Vue d'ensemble de la flotte à un instant t (déterministe)."""

    generated_at: datetime
    poles: tuple[PoleHealth, ...]
    total_facts: int
    total_important: int
    total_critical: int
    poles_red: int
    poles_yellow: int
    poles_active: int

    def by_id(self, pole: str) -> PoleHealth | None:
        return next((p for p in self.poles if p.pole == pole), None)

    @property
    def worst_health(self) -> Health:
        if any(p.health == "critical" for p in self.poles):
            return "critical"
        if any(p.health == "warning" for p in self.poles):
            return "warning"
        if any(p.health == "healthy" for p in self.poles):
            return "healthy"
        return "idle"

    @property
    def red_poles(self) -> list[PoleHealth]:
        return [p for p in self.poles if p.health == "critical"]


def _pole_name(pole: str, *, poles_root: Path) -> str:
    """Nom d'affichage d'un pôle (depuis ``pole.yaml``, fallback = id capitalisé)."""
    try:
        return load_pole_config(pole, poles_root=poles_root).name
    except ConfigError:
        return pole.replace("_", " ").title()


def _headline(records: list[MemoryRecord]) -> str | None:
    """Le fait le plus parlant : critique le plus récent, sinon important, sinon récent."""
    if not records:
        return None
    critical = [r for r in records if fact_severity(r) == "critical"]
    important = [r for r in records if r.important]
    pick = (critical or important or records)[0]  # records déjà triés (récent → vieux)
    body = " ".join(pick.body.split())
    return body[:_HEADLINE_CHARS]


def _pole_health(
    pole: str, by_script: dict[str, list[MemoryRecord]], *, poles_root: Path
) -> PoleHealth:
    records = [r for recs in by_script.values() for r in recs]
    records.sort(key=lambda r: r.created_at, reverse=True)
    severities = [fact_severity(r) for r in records]
    n_critical = sum(1 for s in severities if s == "critical")
    n_warning = sum(1 for s in severities if s == "warning")
    n_important = sum(1 for r in records if r.important)
    if not records:
        health: Health = "idle"
    elif n_critical:
        health = "critical"
    elif n_warning or n_important:
        health = "warning"
    else:
        health = "healthy"
    return PoleHealth(
        pole=pole,
        name=_pole_name(pole, poles_root=poles_root),
        n_facts=len(records),
        n_important=n_important,
        n_critical=n_critical,
        n_warning=n_warning,
        last_activity=(records[0].created_at if records else None),
        health=health,
        headline=_headline(records),
        scripts=tuple(sorted(by_script.keys())),
    )


async def build_fleet_snapshot(
    *,
    poles_root: Path = POLES_DIR,
    include_direction: bool = False,
    now: datetime | None = None,
) -> FleetSnapshot:
    """Construit la vue d'ensemble en lisant la mémoire de tous les pôles.

    ``include_direction=False`` (défaut) exclut le pôle Direction lui-même de la
    liste — la Direction supervise les **autres** pôles. Best-effort : un pôle
    sans mémoire apparaît en ``idle``.
    """
    now = now or datetime.now(UTC)
    poles: list[PoleHealth] = []
    for pole in list_poles(poles_root=poles_root):
        if pole == DIRECTION_POLE and not include_direction:
            continue
        by_script = await read_pole_memory(pole, poles_root=poles_root)
        poles.append(_pole_health(pole, by_script, poles_root=poles_root))
    poles.sort(
        key=lambda p: ({"critical": 0, "warning": 1, "healthy": 2, "idle": 3}[p.health], p.pole)
    )
    return FleetSnapshot(
        generated_at=now,
        poles=tuple(poles),
        total_facts=sum(p.n_facts for p in poles),
        total_important=sum(p.n_important for p in poles),
        total_critical=sum(p.n_critical for p in poles),
        poles_red=sum(1 for p in poles if p.health == "critical"),
        poles_yellow=sum(1 for p in poles if p.health == "warning"),
        poles_active=sum(1 for p in poles if p.health != "idle"),
    )


__all__ = [
    "DIRECTION_POLE",
    "FleetSnapshot",
    "Health",
    "PoleHealth",
    "build_fleet_snapshot",
    "fact_severity",
]
