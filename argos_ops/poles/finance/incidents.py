"""Incidents du pôle Finance (archi v2, S5) — registre légal des post-mortems.

Réutilise telle quelle (pas de re-port) :func:`argos_ops.agents.incident_logger.scaffold_incident`
+ :func:`slugify`, en pointant le dossier sur
``data/poles/finance/incidents/``. Lit le frontmatter des post-mortems existants
pour le cockpit (le registre des incidents est un **document légal** — RGPD art.
33 notification CNIL > 72h —, d'où le flag ``important`` côté mémoire).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

from loguru import logger

from argos_ops.agents.incident_logger import (
    IncidentCategory,
    IncidentScaffold,
    IncidentSeverity,
    scaffold_incident,
    slugify,
)
from argos_ops.poles.config import POLES_DIR
from argos_ops.poles.finance.store import read_markdown

FINANCE_POLE = "finance"


def incidents_dir(*, poles_root: Path = POLES_DIR) -> Path:
    return poles_root / FINANCE_POLE / "incidents"


@dataclass(frozen=True)
class IncidentEntry:
    """Vue cockpit d'un post-mortem d'incident."""

    slug: str
    title: str
    date: str
    category: str
    severity: str
    status: str  # open | resolved | ...


def list_incidents(*, poles_root: Path = POLES_DIR) -> list[IncidentEntry]:
    """Liste les post-mortems (ordre : plus récent d'abord). Best-effort."""
    d = incidents_dir(poles_root=poles_root)
    if not d.exists():
        return []
    out: list[IncidentEntry] = []
    for path in sorted(d.glob("*.md"), reverse=True):
        try:
            fm, _ = read_markdown(path)
        except Exception as exc:  # best-effort
            logger.warning(f"finance/incidents — illisible {path} : {type(exc).__name__}: {exc}")
            continue
        out.append(
            IncidentEntry(
                slug=path.stem,
                title=str(fm.get("title") or path.stem),
                date=str(fm.get("date") or ""),
                category=str(fm.get("category") or "other"),
                severity=str(fm.get("severity") or "P3"),
                status=str(fm.get("status") or "open"),
            )
        )
    return out


def count_open(*, poles_root: Path = POLES_DIR) -> int:
    return sum(1 for i in list_incidents(poles_root=poles_root) if i.status == "open")


def scaffold(
    *,
    title: str,
    category: IncidentCategory,
    severity: IncidentSeverity,
    today: date | None = None,
    poles_root: Path = POLES_DIR,
) -> IncidentScaffold:
    """Scaffold un post-mortem dans le registre Finance (idempotent par jour+slug)."""
    return scaffold_incident(
        title=title,
        category=category,
        severity=severity,
        incidents_dir=incidents_dir(poles_root=poles_root),
        today=today,
    )


__all__ = [
    "IncidentCategory",
    "IncidentEntry",
    "IncidentScaffold",
    "IncidentSeverity",
    "count_open",
    "incidents_dir",
    "list_incidents",
    "scaffold",
    "slugify",
]
