"""Suivi des OKR du pôle Direction (archi v2, S6).

Réutilise la logique pure de :mod:`argos_ops.agents.okr_tracker` (``load_okr``,
``prorata``, ``classify``, ``build_report``, ``KeyResult``, ``OKRReport``,
``KRStatus``) — **aucun re-port** — appliquée à un snapshot local
``data/poles/direction/okr/<YYYY-Qn>.yaml``. Compare la progression de chaque key
result au **prorata temporis** du trimestre.

Ajoute une mutation cockpit déterministe : :func:`set_actual` met à jour la valeur
``actual`` d'un key result (édition depuis le panneau OKR), idempotente et sûre
(ré-écrit le YAML en préservant l'ordre).
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from loguru import logger

from argos_ops.agents.okr_tracker import (
    KeyResult,
    KRStatus,
    OKRReport,
    classify,
    load_okr,
    prorata,
    quarter_bounds,
)
from argos_ops.poles.config import POLES_DIR
from argos_ops.poles.direction.store import dump_yaml_mapping, load_yaml_mapping

DIRECTION_POLE = "direction"


def okr_dir(*, poles_root: Path = POLES_DIR) -> Path:
    return poles_root / DIRECTION_POLE / "okr"


def _detect_quarter(month: int) -> int:
    return (month - 1) // 3 + 1


def current_okr_path(*, poles_root: Path = POLES_DIR, today: date | None = None) -> Path:
    """Chemin du fichier OKR du trimestre courant (convention ``YYYY-Qn.yaml``)."""
    today = today or date.today()
    return okr_dir(poles_root=poles_root) / f"{today.year}-Q{_detect_quarter(today.month)}.yaml"


def load_current(*, poles_root: Path = POLES_DIR, today: date | None = None) -> OKRReport:
    """Charge + évalue les OKR du trimestre courant.

    Résilient (« le transversal ne crashe jamais ») : un YAML OKR mal saisi par le
    fondateur (montant « 10 000 » avec espace, ``actual: TBD``…) ne doit pas faire
    tomber tout le cockpit Direction — :func:`load_okr` coerce ses nombres sans
    garde. On dégrade alors vers un rapport vide signalé plutôt qu'une 500.
    """
    try:
        return load_okr(current_okr_path(poles_root=poles_root, today=today), today=today)
    except (ValueError, TypeError) as exc:
        logger.warning(f"OKR illisible (valeur non numérique ?) — dégradé : {exc}")
        return OKRReport(
            quarter="<illisible>",
            key_results=[],
            should_alert=True,
            alert_color=0,
            summary="OKR illisible — vérifier les valeurs numériques du YAML",
        )


def set_actual(
    objective: str,
    name: str,
    actual: float,
    *,
    poles_root: Path = POLES_DIR,
    today: date | None = None,
) -> OKRReport | None:
    """Met à jour la valeur ``actual`` d'un key result. ``None`` si introuvable.

    Recharge ensuite le rapport pour refléter le nouveau statut (déterministe).
    """
    path = current_okr_path(poles_root=poles_root, today=today)
    raw = load_yaml_mapping(path)
    objectives = raw.get("objectives")
    if not isinstance(objectives, list):
        return None
    touched = False
    for obj in objectives:
        if not isinstance(obj, dict) or str(obj.get("title") or "") != objective:
            continue
        krs = obj.get("key_results")
        if not isinstance(krs, list):
            continue
        for kr in krs:
            if isinstance(kr, dict) and str(kr.get("name") or "") == name:
                kr["actual"] = actual
                touched = True
    if not touched:
        return None
    dump_yaml_mapping(path, raw)
    return load_current(poles_root=poles_root, today=today)


__all__ = [
    "KRStatus",
    "KeyResult",
    "OKRReport",
    "classify",
    "current_okr_path",
    "load_current",
    "okr_dir",
    "prorata",
    "quarter_bounds",
    "set_actual",
]
