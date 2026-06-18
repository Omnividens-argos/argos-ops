"""Garde-fou de **publication** du pôle Direction (archi v2, S6).

**Garde-fou central du pôle (« le LLM propose, Python tranche »)** — l'analogue
du gel Bloctel de la Vente / de la conformité de la Finance / du breaker
``ad_spend_runaway`` de Pub.

La Direction est le pôle qui **publie vers l'extérieur** des artefacts produit
(release notes, changelog, roadmap publique). On **gèle** cette publication tant
que la flotte n'est pas en état d'être montrée :

- un **bug P0 ouvert** (:func:`argos_ops.poles.direction.bugs.open_p0`) — on ne
  communique pas de nouveautés pendant qu'une régression critique est en cours ;
- **ou** au moins un pôle en santé **critique** (:class:`FleetSnapshot` —
  conformité gelée, breaker tripped, SLA breach, runway sous seuil…).

Le ``DirectionAgent`` marque alors toute action de **publication** comme
``suppressed_by_release`` ; le cerveau (``claude -p``, D-017) peut réordonner les
priorités mais ne peut **jamais** lever ce gel. La logique cœur est pure
(:func:`evaluate`) — testable offline ; les wrappers async ne font que charger le
snapshot.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

from argos_ops.poles.config import POLES_DIR
from argos_ops.poles.direction import bugs
from argos_ops.poles.direction.fleet import FleetSnapshot, build_fleet_snapshot


@dataclass(frozen=True)
class ReleaseGate:
    """État du garde-fou de publication (déterministe)."""

    blocking: bool
    reason: str
    open_p0: int
    red_poles: tuple[str, ...]


def evaluate(snapshot: FleetSnapshot, open_p0: int) -> ReleaseGate:
    """Décide si la publication est gelée — logique pure (sans I/O)."""
    red = tuple(p.name for p in snapshot.red_poles)
    reasons: list[str] = []
    if open_p0 > 0:
        reasons.append(f"{open_p0} bug(s) P0 ouvert(s)")
    if red:
        reasons.append(f"{len(red)} pôle(s) en alerte critique : {', '.join(red)}")
    return ReleaseGate(
        blocking=bool(reasons),
        reason=" ; ".join(reasons),
        open_p0=open_p0,
        red_poles=red,
    )


async def gate(*, poles_root: Path = POLES_DIR, today: date | None = None) -> ReleaseGate:
    """Évalue le garde-fou en chargeant le snapshot flotte + le compte de P0."""
    snapshot = await build_fleet_snapshot(poles_root=poles_root)
    return evaluate(snapshot, bugs.open_p0(poles_root=poles_root))


async def release_blocking(*, poles_root: Path = POLES_DIR, today: date | None = None) -> bool:
    """``True`` si la publication d'artefacts publics est gelée."""
    return (await gate(poles_root=poles_root, today=today)).blocking


async def blocking_reason(*, poles_root: Path = POLES_DIR, today: date | None = None) -> str:
    """Phrase courte expliquant le gel (vide si non bloquant)."""
    return (await gate(poles_root=poles_root, today=today)).reason


__all__ = [
    "ReleaseGate",
    "blocking_reason",
    "evaluate",
    "gate",
    "release_blocking",
]
