"""``KillSwitchOperatorScript`` — breakers armés trop longtemps (archi v2, S8).

Surveille le registre de breakers (:mod:`argos_ops.poles.sre.breakers`) et alerte
sur ceux armés depuis trop longtemps : jaune ≥ 4 h, rouge ≥ 24 h. Rappelle le
reset cockpit (``/reset-breaker <name>``). Lecture pure du registre fichier — ne
désarme jamais lui-même (le reset est une décision humaine).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from argos_ops.poles.sre import breakers
from argos_ops.poles.sre.base import BaseSreScript
from argos_ops.poles.sre.breakers import Breaker
from argos_ops.poles.sre.report import Severity, SreReport

MIN_STALE_HOURS = 4.0
CRITICAL_STALE_HOURS = 24.0


@dataclass(frozen=True)
class StaleBreaker:
    """Un breaker armé au-delà du seuil de surveillance."""

    name: str
    reason: str | None
    age_hours: float


def find_stale(tripped: list[Breaker], *, now: datetime) -> list[StaleBreaker]:
    """Filtre les breakers armés depuis ≥ MIN_STALE_HOURS (pur). Plus vieux d'abord."""
    stale: list[StaleBreaker] = []
    for b in tripped:
        if b.tripped_at is None:
            continue
        age = (now - b.tripped_at).total_seconds() / 3600.0
        if age >= MIN_STALE_HOURS:
            stale.append(StaleBreaker(b.name, b.reason, age))
    stale.sort(key=lambda s: -s.age_hours)
    return stale


def _age_band(age_hours: float) -> str:
    """Bande d'âge stable (≥ 24h / ≥ 4h) — évite l'âge précis dans le corps mémoire."""
    return ">= 24h" if age_hours >= CRITICAL_STALE_HOURS else ">= 4h"


def build_report(stale: list[StaleBreaker]) -> SreReport:
    if not stale:
        return SreReport("green", "Aucun breaker armé depuis trop longtemps.")
    has_critical = any(s.age_hours >= CRITICAL_STALE_HOURS for s in stale)
    severity: Severity = "red" if has_critical else "yellow"
    summary = f"{len(stale)} breaker(s) armé(s) ≥ {MIN_STALE_HOURS:.0f}h — reset cockpit requis"
    # Détail STABLE : bande d'âge (≥ 4h / ≥ 24h), pas l'âge précis live ⇒ le corps
    # mémoire reste idempotent tant que la bande ne franchit pas le seuil critique.
    detail = "\n".join(
        f"- {s.name} : {_age_band(s.age_hours)}"
        + (f" — {s.reason}" if s.reason else "")
        + f" → /reset-breaker {s.name}"
        for s in stale
    )
    return SreReport(severity, summary, detail)


class KillSwitchOperatorScript(BaseSreScript):
    """Alerte sur les breakers armés trop longtemps."""

    name = "kill_switch_operator"

    async def check(self) -> SreReport:
        now = datetime.now(UTC)
        tripped = breakers.list_tripped(poles_root=self.poles_root)
        return build_report(find_stale(tripped, now=now))


__all__ = [
    "CRITICAL_STALE_HOURS",
    "MIN_STALE_HOURS",
    "KillSwitchOperatorScript",
    "StaleBreaker",
    "build_report",
    "find_stale",
]
