"""Agrégation du feedback produit — pôle Direction (archi v2, S6).

Réutilise la logique pure de :mod:`argos_ops.agents.feedback_aggregator`
(``aggregate``, ``FeedbackTheme``, ``render_digest``, ``FeedbackReport``) —
**aucun re-port** — sur un snapshot local ``data/poles/direction/feedback/items.yaml``.
Cluster les demandes clients par ``topic`` ; un thème **récurrent** (≥ 2 mentions)
devient un fait ``important`` côté script (signal d'arbitrage produit).

Format YAML attendu ::

    items:
      - source: email           # email | support | discord | call
        customer_id: acme-sa
        date: 2026-06-10
        topic: Export PDF en français
        verbatim: "On aimerait l'export rapport en FR."
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

from argos_ops.agents.feedback_aggregator import (
    FeedbackReport,
    FeedbackTheme,
    aggregate,
    render_digest,
)
from argos_ops.poles.config import POLES_DIR
from argos_ops.poles.direction.store import load_yaml_mapping

DIRECTION_POLE = "direction"

# Seuil de récurrence au-delà duquel un thème mérite d'être retenu (fait important).
MIN_MENTIONS_RECURRING = 2


def feedback_path(*, poles_root: Path = POLES_DIR) -> Path:
    return poles_root / DIRECTION_POLE / "feedback" / "items.yaml"


def load_items(*, poles_root: Path = POLES_DIR) -> list[dict[str, Any]]:
    """Lit les items de feedback (vide si absent / mal typé)."""
    raw = load_yaml_mapping(feedback_path(poles_root=poles_root))
    items = raw.get("items")
    if not isinstance(items, list):
        return []
    return [i for i in items if isinstance(i, dict)]


def themes(*, poles_root: Path = POLES_DIR) -> list[FeedbackTheme]:
    """Thèmes agrégés (tri par nombre de mentions décroissant)."""
    return aggregate(load_items(poles_root=poles_root))


def build_report(*, poles_root: Path = POLES_DIR) -> FeedbackReport:
    """Rapport complet (items + thèmes) pour le digest / cockpit."""
    items = load_items(poles_root=poles_root)
    return FeedbackReport(items_total=len(items), themes=aggregate(items))


def recurring_themes(*, poles_root: Path = POLES_DIR) -> list[FeedbackTheme]:
    """Thèmes récurrents (≥ seuil de mentions) — alimentent un fait important."""
    return [t for t in themes(poles_root=poles_root) if t.count >= MIN_MENTIONS_RECURRING]


def digest_markdown(*, poles_root: Path = POLES_DIR, today: date | None = None) -> str:
    """Digest markdown du feedback (réutilise le rendu legacy)."""
    return render_digest(build_report(poles_root=poles_root), today=today or date.today())


__all__ = [
    "MIN_MENTIONS_RECURRING",
    "FeedbackReport",
    "FeedbackTheme",
    "build_report",
    "digest_markdown",
    "feedback_path",
    "load_items",
    "recurring_themes",
    "themes",
]
