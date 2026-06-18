"""Historique **append-only** des passages du cleaner (archi v2, S7).

Chaque suppression validée (ou refusée par garde-fou) est journalisée dans
``data/poles/memoire/history.jsonl`` — 1 ligne JSON par run. Le cockpit
(onglet Mémoire → Historique) relit ce journal, du plus récent au plus ancien.

Append-only : on n'édite/supprime jamais une ligne — c'est la trace d'audit de
l'unique pôle autorisé à supprimer un fait. Lecture best-effort : une ligne
illisible est loguée et sautée, jamais fatale.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from loguru import logger

from argos_ops.poles.config import POLES_DIR
from argos_ops.poles.memoire.policy import MEMOIRE_POLE

HISTORY_FILE = "history.jsonl"


def history_path(*, poles_root: Path = POLES_DIR) -> Path:
    return poles_root / MEMOIRE_POLE / HISTORY_FILE


@dataclass(frozen=True)
class HistoryItem:
    """Un fait supprimé (ou refusé) dans un run."""

    script: str
    record_id: str
    kind: str
    reason: str  # expired | stale (supprimé) — ou motif de refus


@dataclass(frozen=True)
class HistoryEntry:
    """Un passage du cleaner sur un pôle."""

    at: datetime
    pole: str
    actor: str
    deleted: tuple[HistoryItem, ...]
    refused: tuple[HistoryItem, ...]

    @property
    def n_deleted(self) -> int:
        return len(self.deleted)

    @property
    def n_refused(self) -> int:
        return len(self.refused)


def _item_to_dict(item: HistoryItem) -> dict[str, str]:
    return {
        "script": item.script,
        "record_id": item.record_id,
        "kind": item.kind,
        "reason": item.reason,
    }


def _item_from_dict(raw: object) -> HistoryItem | None:
    if not isinstance(raw, dict):
        return None
    return HistoryItem(
        script=str(raw.get("script", "")),
        record_id=str(raw.get("record_id", "")),
        kind=str(raw.get("kind", "")),
        reason=str(raw.get("reason", "")),
    )


def append_run(
    pole: str,
    *,
    actor: str,
    deleted: tuple[HistoryItem, ...],
    refused: tuple[HistoryItem, ...],
    at: datetime | None = None,
    poles_root: Path = POLES_DIR,
) -> HistoryEntry:
    """Journalise un passage du cleaner (append 1 ligne JSON). Retourne l'entrée."""
    entry = HistoryEntry(
        at=at or datetime.now(UTC),
        pole=pole,
        actor=actor,
        deleted=deleted,
        refused=refused,
    )
    payload = {
        "at": entry.at.isoformat(),
        "pole": entry.pole,
        "actor": entry.actor,
        "deleted": [_item_to_dict(i) for i in deleted],
        "refused": [_item_to_dict(i) for i in refused],
    }
    path = history_path(poles_root=poles_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, ensure_ascii=False) + "\n")
    logger.debug(f"memoire.history : run journalisé ({pole}, {len(deleted)} supprimé(s))")
    return entry


def _entry_from_line(line: str) -> HistoryEntry | None:
    raw = json.loads(line)
    if not isinstance(raw, dict):
        return None
    try:
        at = datetime.fromisoformat(str(raw["at"]))
    except (KeyError, ValueError):
        return None
    if at.tzinfo is None:
        at = at.replace(tzinfo=UTC)
    deleted = tuple(i for i in map(_item_from_dict, raw.get("deleted") or []) if i is not None)
    refused = tuple(i for i in map(_item_from_dict, raw.get("refused") or []) if i is not None)
    return HistoryEntry(
        at=at,
        pole=str(raw.get("pole", "")),
        actor=str(raw.get("actor", "")),
        deleted=deleted,
        refused=refused,
    )


def load_runs(*, limit: int | None = None, poles_root: Path = POLES_DIR) -> list[HistoryEntry]:
    """Relit l'historique, du plus récent au plus ancien. ``limit`` borne le retour."""
    path = history_path(poles_root=poles_root)
    if not path.exists():
        return []
    entries: list[HistoryEntry] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            entry = _entry_from_line(line)
        except json.JSONDecodeError as exc:
            logger.warning(f"memoire.history : ligne illisible sautée — {exc}")
            continue
        if entry is not None:
            entries.append(entry)
    entries.sort(key=lambda e: e.at, reverse=True)
    return entries[:limit] if limit is not None else entries


__all__ = [
    "HISTORY_FILE",
    "HistoryEntry",
    "HistoryItem",
    "append_run",
    "history_path",
    "load_runs",
]
