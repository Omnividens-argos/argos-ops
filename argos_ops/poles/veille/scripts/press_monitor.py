"""``PressMonitorScript`` — mentions presse Argos / Omnividens (Veille, archi v2).

Porté depuis ``argos_ops.agents.press_monitor`` (legacy). Bras déterministe,
mode shadow strict (pas de scraper généraliste) :

1. lit ``data/comm/press_mentions.yaml`` (alimenté manuellement depuis Google
   Alerts ou veille founder) via :func:`load_mentions` ;
2. filtre les nouvelles entrées (``status: new``) et écrit un fait par mention
   dans **sa propre mémoire de pôle** (``kind="press"``) ;
3. marque les entrées traitées ``status: ack`` en réécrivant le YAML, exactement
   comme le bot legacy (:func:`mark_ack`).

Pas de Discord, pas de DB, pas de LLM (D-017) : le :class:`VeilleAgent` lit cette
mémoire et agit. La sévérité (sentiment négatif) est encodée via le flag
``important`` + le tag ``sentiment``. Idempotent : une mention déjà acquittée
n'est plus ``new`` au run suivant, et le corps du fait est stable (le socle
:func:`argos_ops.poles.memory.write_memory` déduplique par hash).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from argos_ops.config import REPO_ROOT
from argos_ops.poles.base import BaseScript, ScriptResult
from argos_ops.poles.config import POLES_DIR

MENTIONS_PATH = REPO_ROOT / "data" / "comm" / "press_mentions.yaml"


@dataclass
class PressMention:
    """Une mention presse lue depuis ``press_mentions.yaml`` (founder-maintained)."""

    id: str
    source: str
    url: str
    title: str
    sentiment: str = "neutral"
    status: str = "new"


def load_mentions(path: Path | None = None) -> list[PressMention]:
    """Parse les mentions presse depuis le YAML (best-effort, ignore l'invalide)."""
    path = path or MENTIONS_PATH
    if not path.exists():
        return []
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    out: list[PressMention] = []
    for entry in raw.get("mentions", []):
        if not isinstance(entry, dict):
            continue
        try:
            out.append(
                PressMention(
                    id=str(entry["id"]),
                    source=str(entry.get("source", "")),
                    url=str(entry.get("url", "")),
                    title=str(entry.get("title", "")),
                    sentiment=str(entry.get("sentiment", "neutral")),
                    status=str(entry.get("status", "new")),
                )
            )
        except KeyError:
            continue
    return out


def mark_ack(mentions: list[PressMention], ack_ids: set[str], path: Path | None = None) -> None:
    """Réécrit le YAML en passant ``ack_ids`` à ``status: ack`` (snapshot state)."""
    path = path or MENTIONS_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    out: list[dict[str, object]] = []
    for m in mentions:
        status = "ack" if m.id in ack_ids else m.status
        out.append(
            {
                "id": m.id,
                "source": m.source,
                "url": m.url,
                "title": m.title,
                "sentiment": m.sentiment,
                "status": status,
            }
        )
    path.write_text(yaml.safe_dump({"mentions": out}, allow_unicode=True), encoding="utf-8")


class PressMonitorScript(BaseScript):
    """Détecte les nouvelles mentions presse et les mémorise (``kind="press"``)."""

    pole = "veille"
    name = "press_monitor"

    def __init__(
        self,
        *,
        poles_root: Path = POLES_DIR,
        mentions_path: Path | None = None,
    ) -> None:
        super().__init__(poles_root=poles_root)
        self._mentions_path = mentions_path or MENTIONS_PATH

    async def run(self) -> ScriptResult:
        mentions = load_mentions(self._mentions_path)
        new = [m for m in mentions if m.status == "new"]

        written = []
        for m in new:
            record = await self.write_memory(
                f"Mention presse [{m.source}] {m.title} ({m.sentiment}) - {m.url}",
                kind="press",
                tags=("press", m.sentiment),
                important=m.sentiment == "negative",
                source=m.url or self.name,
            )
            written.append(record)

        if new:
            mark_ack(mentions, ack_ids={m.id for m in new}, path=self._mentions_path)

        negatives = sum(1 for m in new if m.sentiment == "negative")
        return ScriptResult(
            status="success",
            summary=f"total={len(mentions)} new={len(new)} negatives={negatives}",
            written=written,
        )


__all__ = [
    "MENTIONS_PATH",
    "PressMention",
    "PressMonitorScript",
    "load_mentions",
    "mark_ack",
]
