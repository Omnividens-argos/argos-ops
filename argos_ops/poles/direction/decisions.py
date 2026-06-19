"""Journal des décisions du pôle Direction (archi v2, S6).

Réutilise la logique pure de :mod:`argos_ops.agents.decision_logger`
(``find_next_decision_id``, ``render_decision``, ``append_decision``,
``DecisionDraft``) — **aucun re-port** — sur un journal **local** au pôle
``data/poles/direction/decisions/journal.md`` (et non le ``docs/DECISIONS.md``
canonique : le pôle reste autonome, et l'écriture cockpit ne touche jamais la
doc du repo).

Expose en plus un parseur léger :func:`load_decisions` qui relit le journal en
entrées structurées pour l'affichage cockpit (timeline).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from argos_ops.agents.decision_logger import (
    DecisionDraft,
    DecisionWriteResult,
    append_decision,
    find_next_decision_id,
    render_decision,
)
from argos_ops.poles.config import POLES_DIR
from argos_ops.poles.direction.store import dump_yaml_mapping, load_yaml_mapping

DIRECTION_POLE = "direction"

#: Statuts valides du cycle de vie d'une décision (sidecar additif).
DECISION_STATUSES = ("open", "closed")
#: Statut par défaut quand une décision n'a pas d'entrée dans le sidecar.
DEFAULT_DECISION_STATUS = "open"

_BLOCK_RE = re.compile(r"^##\s+(D-\d{3})\s+—\s+(.+?)\s*$", re.MULTILINE)
_FIELD_RE = {
    "date": re.compile(r"^\*\*Date :\*\*\s*(.+?)\s*$", re.MULTILINE),
    "partie": re.compile(r"^\*\*Partie :\*\*\s*(.+?)\s*$", re.MULTILINE),
    "decision": re.compile(r"^\*\*Décision :\*\*\s*(.+?)\s*$", re.MULTILINE),
}


@dataclass(frozen=True)
class DecisionEntry:
    """Une décision lue du journal (vue cockpit)."""

    decision_id: str
    title: str
    decision_date: str
    partie: str
    decision: str


def journal_path(*, poles_root: Path = POLES_DIR) -> Path:
    return poles_root / DIRECTION_POLE / "decisions" / "journal.md"


def _field(block: str, key: str) -> str:
    match = _FIELD_RE[key].search(block)
    return match.group(1).strip() if match else ""


def load_decisions(*, poles_root: Path = POLES_DIR) -> list[DecisionEntry]:
    """Relit le journal en entrées structurées (plus récent d'ID en tête)."""
    path = journal_path(poles_root=poles_root)
    if not path.exists():
        return []
    content = path.read_text(encoding="utf-8")
    headers = list(_BLOCK_RE.finditer(content))
    entries: list[DecisionEntry] = []
    for i, m in enumerate(headers):
        start = m.end()
        end = headers[i + 1].start() if i + 1 < len(headers) else len(content)
        block = content[start:end]
        entries.append(
            DecisionEntry(
                decision_id=m.group(1),
                title=m.group(2).strip(),
                decision_date=_field(block, "date"),
                partie=_field(block, "partie"),
                decision=_field(block, "decision"),
            )
        )
    entries.sort(key=lambda e: e.decision_id, reverse=True)
    return entries


def log_decision(
    draft: DecisionDraft, *, poles_root: Path = POLES_DIR, today: date | None = None
) -> DecisionWriteResult:
    """Append une décision au journal local du pôle (idempotent par titre)."""
    return append_decision(draft, output_path=journal_path(poles_root=poles_root), today=today)


def status_path(*, poles_root: Path = POLES_DIR) -> Path:
    """Chemin du sidecar additif des statuts (open/closed) par décision."""
    return poles_root / DIRECTION_POLE / "decision_status.yaml"


def load_statuses(*, poles_root: Path = POLES_DIR) -> dict[str, str]:
    """Relit le sidecar des statuts en mapping ``{decision_id: status}``.

    Best-effort : un fichier absent / illisible donne un mapping vide (toute
    décision est alors « open » par défaut). Seules les valeurs valides
    (:data:`DECISION_STATUSES`) sont conservées.
    """
    raw = load_yaml_mapping(status_path(poles_root=poles_root))
    statuses: dict[str, str] = {}
    for key, value in raw.items():
        status = str(value)
        if status in DECISION_STATUSES:
            statuses[str(key)] = status
    return statuses


def set_status(decision_id: str, status: str, *, poles_root: Path = POLES_DIR) -> dict[str, str]:
    """Persiste le statut d'une décision dans le sidecar (idempotent).

    Réécrit l'intégralité du mapping (ordre des clés préservé) et renvoie le
    mapping à jour. ``status`` doit appartenir à :data:`DECISION_STATUSES` —
    la validation des entrées (id connu, statut valide) reste à la charge de
    l'appelant (le routeur tranche les codes HTTP).
    """
    statuses = load_statuses(poles_root=poles_root)
    statuses[decision_id] = status
    dump_yaml_mapping(status_path(poles_root=poles_root), statuses)
    return statuses


__all__ = [
    "DECISION_STATUSES",
    "DEFAULT_DECISION_STATUS",
    "DecisionDraft",
    "DecisionEntry",
    "DecisionWriteResult",
    "find_next_decision_id",
    "journal_path",
    "load_decisions",
    "load_statuses",
    "log_decision",
    "render_decision",
    "set_status",
    "status_path",
]
