"""Roadmap publique — pôle Direction (archi v2, S6).

Réutilise la logique pure de :mod:`argos_ops.product.annexe_d_parser`
(``parse_annexe_d``, ``count_states``, ``BotEntry``) et le rendu de
:func:`argos_ops.agents.roadmap_publisher.render_public_roadmap` — **aucun
re-port**. En local-first, parse un snapshot ``data/poles/direction/roadmap/annexe_d.md``
(extrait de l'Annexe D interne, source unique d'avancement) et publie une roadmap
**épurée des codes sprint** internes.

C'est un **artefact public** : sa publication (génération) est soumise au
garde-fou :func:`argos_ops.poles.direction.release.release_blocking`.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from argos_ops.agents.roadmap_publisher import render_public_roadmap
from argos_ops.poles.config import POLES_DIR
from argos_ops.product.annexe_d_parser import BotEntry, count_states, parse_annexe_d

DIRECTION_POLE = "direction"


@dataclass(frozen=True)
class RoadmapView:
    """Roadmap publique rendue + compteurs d'état."""

    entries_total: int
    done: int
    partial: int
    roadmap: int
    services: int
    markdown: str


def annexe_path(*, poles_root: Path = POLES_DIR) -> Path:
    return poles_root / DIRECTION_POLE / "roadmap" / "annexe_d.md"


def load_entries(*, poles_root: Path = POLES_DIR) -> list[BotEntry]:
    """Parse les entrées de l'Annexe D locale (vide si absente)."""
    return parse_annexe_d(annexe_path(poles_root=poles_root))


def build_roadmap(*, poles_root: Path = POLES_DIR) -> RoadmapView:
    """Construit la roadmap publique markdown + compteurs."""
    entries = load_entries(poles_root=poles_root)
    counts = count_states(entries)
    services = {e.service for e in entries}
    return RoadmapView(
        entries_total=len(entries),
        done=counts["done"],
        partial=counts["partial"],
        roadmap=counts["roadmap"],
        services=len(services),
        markdown=render_public_roadmap(entries),
    )


__all__ = ["RoadmapView", "annexe_path", "build_roadmap", "load_entries"]
