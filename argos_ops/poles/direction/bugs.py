"""Triage des bugs du pôle Direction (archi v2, S6).

Réutilise la logique pure de classification de :mod:`argos_ops.agents.bug_triage`
(``classify_severity`` mots-clés, ``triage_issues``, ``TriagedIssue``,
``BugTriageStats``) — **aucun re-port** — appliquée à un snapshot local
``data/poles/direction/bugs/issues.yaml`` (saisie manuelle / export
``gh issue list``). 100 % déterministe (pas de fetch GitHub ni de cerveau ici :
le bras du pôle reste pur ; l'enrichissement LLM resterait au niveau agent).

Le nombre de **P0 ouverts** alimente le garde-fou
:func:`argos_ops.poles.direction.release.release_blocking`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from argos_ops.agents.bug_triage import BugTriageStats, triage_issues
from argos_ops.poles.config import POLES_DIR
from argos_ops.poles.direction.store import load_yaml_mapping

DIRECTION_POLE = "direction"


def issues_path(*, poles_root: Path = POLES_DIR) -> Path:
    return poles_root / DIRECTION_POLE / "bugs" / "issues.yaml"


def load_issues(*, poles_root: Path = POLES_DIR) -> list[dict[str, Any]]:
    """Lit les issues ouvertes du snapshot local (vide si absent / mal typé)."""
    raw = load_yaml_mapping(issues_path(poles_root=poles_root))
    issues = raw.get("issues")
    if not isinstance(issues, list):
        return []
    return [i for i in issues if isinstance(i, dict)]


def triage(*, poles_root: Path = POLES_DIR) -> BugTriageStats:
    """Trie les issues locales par sévérité (P0/P1/P2) via les mots-clés legacy."""
    return triage_issues(load_issues(poles_root=poles_root))


def open_p0(*, poles_root: Path = POLES_DIR) -> int:
    """Nombre de bugs P0 ouverts (alimente le garde-fou de publication)."""
    return triage(poles_root=poles_root).p0


__all__ = ["BugTriageStats", "issues_path", "load_issues", "open_p0", "triage"]
