"""``MediaListBuilderScript`` — audit de la DB journalistes / médias cyber.

Porté depuis ``argos_ops.agents.media_list_builder``, en local-first self-contained.
Bras déterministe (mode shadow strict — aucun scraping) :

1. lit la DB founder-maintained ``data/comm/media_list.yaml`` (overridable) ;
2. calcule la complétude des fiches (email + beat) et la répartition par beat ;
3. écrit un fait d'audit dans **sa propre mémoire** (``kind="media"``), flaggé
   ``important`` si la DB est sous le seuil (< 10 contacts) ou a des trous.

Pas de Discord, pas de DB (D-017). Idempotent : même DB ⇒ même corps de fait.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from loguru import logger

from argos_ops.config import REPO_ROOT
from argos_ops.poles.base import BaseScript, ScriptResult
from argos_ops.poles.config import POLES_DIR

DEFAULT_MEDIA_LIST = REPO_ROOT / "data" / "comm" / "media_list.yaml"
_MIN_CONTACTS = 10


@dataclass(frozen=True)
class MediaContact:
    slug: str
    name: str
    outlet: str = ""
    beat: str = ""
    email: str = ""

    @property
    def is_complete(self) -> bool:
        return bool(self.email and self.beat)


@dataclass
class MediaReport:
    total: int = 0
    by_beat: Counter[str] = field(default_factory=Counter)
    incomplete: list[str] = field(default_factory=list)

    @property
    def has_signal(self) -> bool:
        return self.total < _MIN_CONTACTS or len(self.incomplete) > 0

    def summary(self) -> str:
        breakdown = ", ".join(f"{k}={v}" for k, v in self.by_beat.most_common()) or "aucun beat"
        return (
            f"DB médias : {self.total} contact(s), {len(self.incomplete)} incomplet(s) "
            f"({breakdown})"
        )


def load_media_list(path: Path) -> list[MediaContact]:
    """Charge la DB médias. Best-effort (fiches malformées ignorées)."""
    if not path.exists():
        return []
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        logger.warning(f"media list — YAML invalide {path} : {exc}")
        return []
    out: list[MediaContact] = []
    for entry in raw.get("contacts", []) if isinstance(raw, dict) else []:
        if not isinstance(entry, dict) or "slug" not in entry:
            continue
        out.append(
            MediaContact(
                slug=str(entry["slug"]),
                name=str(entry.get("name", "")),
                outlet=str(entry.get("outlet", "")),
                beat=str(entry.get("beat", "")),
                email=str(entry.get("email", "")),
            )
        )
    return out


def build_report(contacts: list[MediaContact]) -> MediaReport:
    report = MediaReport(total=len(contacts))
    for c in contacts:
        if c.beat:
            report.by_beat[c.beat] += 1
        if not c.is_complete:
            report.incomplete.append(c.slug)
    return report


class MediaListBuilderScript(BaseScript):
    """Audite la complétude de la DB journalistes / médias (``kind="media"``)."""

    pole = "marketing"
    name = "media_list_builder"

    def __init__(
        self,
        *,
        poles_root: Path = POLES_DIR,
        media_list_path: Path | None = None,
    ) -> None:
        super().__init__(poles_root=poles_root)
        self._media_list_path = media_list_path or DEFAULT_MEDIA_LIST

    async def run(self) -> ScriptResult:
        contacts = load_media_list(self._media_list_path)
        if not contacts:
            return ScriptResult(
                status="success",
                summary="DB médias absente ou vide — rien à auditer.",
                written=[],
            )
        report = build_report(contacts)
        record = await self.write_memory(
            report.summary(),
            kind="media",
            tags=("media", "incomplete") if report.incomplete else ("media",),
            important=report.has_signal,
        )
        return ScriptResult(status="success", summary=report.summary(), written=[record])


__all__ = [
    "MediaContact",
    "MediaListBuilderScript",
    "MediaReport",
    "build_report",
    "load_media_list",
]
