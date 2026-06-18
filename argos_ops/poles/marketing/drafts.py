"""File de **drafts** éditoriaux du pôle Marketing (archi v2, S2).

Un draft = un contenu rédigé (par l'agent via un skill writer, ou à la main)
**en attente de validation humaine** (D-017, humain-in-the-loop). Stocké en
fichier markdown ``data/poles/marketing/drafts/<id>.md`` (frontmatter + corps).

Cycle de vie ::

    draft ──valider──▶ validated ──(ContentBot publie)──▶ published
      └────rejeter────▶ rejected

Module *pur* (fichiers only) partagé par le cockpit (file de validation inline,
calendrier éditorial drag-and-drop, preview par canal) **et** par le script
:class:`~argos_ops.poles.marketing.scripts.content_bot.ContentBotScript` qui
publie les ``validated`` dont ``scheduled_for`` est échu.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from loguru import logger

from argos_ops.poles.config import POLES_DIR
from argos_ops.poles.marketing.store import read_markdown, write_markdown

DRAFTS_DIRNAME = "drafts"
MARKETING_POLE = "marketing"

DraftStatus = Literal["draft", "validated", "rejected", "published"]
DRAFT_STATUSES: tuple[DraftStatus, ...] = ("draft", "validated", "rejected", "published")

_SLUG_MAX = 48


def _utcnow() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True)
class Draft:
    """Un contenu éditorial en attente de validation / publication."""

    id: str
    channel: str
    title: str
    body: str
    status: DraftStatus = "draft"
    writer: str | None = None
    source: str | None = None
    scheduled_for: datetime | None = None
    created_at: datetime = field(default_factory=_utcnow)
    updated_at: datetime = field(default_factory=_utcnow)


# =============================================================================
# Identité / chemins
# =============================================================================
def slugify(text: str) -> str:
    """Slug kebab-case stable (ascii, borné) pour dériver un id de draft.

    Translittère les accents (``é`` → ``e``) avant de réduire en kebab-case, pour
    des slugs propres (``nis2-expliquee`` plutôt que ``nis2-expliqu-e``).
    """
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    norm = re.sub(r"[^a-z0-9]+", "-", ascii_text.strip().lower()).strip("-")
    return norm[:_SLUG_MAX] or "draft"


def make_draft_id(channel: str, title: str) -> str:
    """``<canal>-<slug-du-titre>`` — stable et lisible."""
    return f"{channel}-{slugify(title)}"


def drafts_dir(*, poles_root: Path = POLES_DIR) -> Path:
    return poles_root / MARKETING_POLE / DRAFTS_DIRNAME


def _draft_path(draft_id: str, *, poles_root: Path) -> Path:
    return drafts_dir(poles_root=poles_root) / f"{draft_id}.md"


# =============================================================================
# (Dé)sérialisation
# =============================================================================
def _parse_dt(value: object) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    try:
        dt = datetime.fromisoformat(str(value))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def _coerce_status(value: object) -> DraftStatus:
    raw = str(value or "draft")
    return raw if raw in DRAFT_STATUSES else "draft"


def _draft_to_fm(draft: Draft) -> dict[str, object]:
    return {
        "id": draft.id,
        "channel": draft.channel,
        "title": draft.title,
        "status": draft.status,
        "writer": draft.writer,
        "source": draft.source,
        "scheduled_for": draft.scheduled_for.isoformat() if draft.scheduled_for else None,
        "created_at": draft.created_at.isoformat(),
        "updated_at": draft.updated_at.isoformat(),
    }


# =============================================================================
# Lecture
# =============================================================================
def _read_draft_file(path: Path) -> Draft:
    fm, body = read_markdown(path)
    created = _parse_dt(fm.get("created_at")) or _utcnow()
    updated = _parse_dt(fm.get("updated_at")) or created
    return Draft(
        id=str(fm.get("id") or path.stem),
        channel=str(fm.get("channel") or "linkedin"),
        title=str(fm.get("title") or ""),
        body=body.strip(),
        status=_coerce_status(fm.get("status")),
        writer=(str(fm["writer"]) if fm.get("writer") else None),
        source=(str(fm["source"]) if fm.get("source") else None),
        scheduled_for=_parse_dt(fm.get("scheduled_for")),
        created_at=created,
        updated_at=updated,
    )


def load_drafts(*, poles_root: Path = POLES_DIR) -> list[Draft]:
    """Tous les drafts (du plus récent au plus ancien). Best-effort."""
    d = drafts_dir(poles_root=poles_root)
    if not d.exists():
        return []
    out: list[Draft] = []
    for path in d.glob("*.md"):
        try:
            out.append(_read_draft_file(path))
        except Exception as exc:  # best-effort, comme la mémoire
            logger.warning(f"drafts — fichier illisible {path} : {type(exc).__name__}: {exc}")
    out.sort(key=lambda dr: dr.created_at, reverse=True)
    return out


def load_draft(draft_id: str, *, poles_root: Path = POLES_DIR) -> Draft | None:
    path = _draft_path(draft_id, poles_root=poles_root)
    if not path.exists():
        return None
    return _read_draft_file(path)


# =============================================================================
# Écriture / mutations
# =============================================================================
def write_draft(draft: Draft, *, poles_root: Path = POLES_DIR) -> Draft:
    """Persiste un draft (crée le dossier). Bas niveau."""
    write_markdown(_draft_path(draft.id, poles_root=poles_root), _draft_to_fm(draft), draft.body)
    logger.debug(f"draft write — {draft.id} ({draft.status})")
    return draft


def create_draft(
    *,
    channel: str,
    title: str,
    body: str,
    writer: str | None = None,
    source: str | None = None,
    poles_root: Path = POLES_DIR,
) -> Draft:
    """Crée (ou écrase) un draft ``status=draft`` à partir d'un canal + titre."""
    draft = Draft(
        id=make_draft_id(channel, title),
        channel=channel,
        title=title,
        body=body,
        status="draft",
        writer=writer,
        source=source,
    )
    return write_draft(draft, poles_root=poles_root)


def _mutate(
    draft_id: str,
    *,
    poles_root: Path,
    status: DraftStatus | None = None,
    title: str | None = None,
    body: str | None = None,
    scheduled_for: datetime | None = None,
    clear_schedule: bool = False,
) -> Draft | None:
    prev = load_draft(draft_id, poles_root=poles_root)
    if prev is None:
        logger.warning(f"draft mutate — introuvable : {draft_id}")
        return None
    new_schedule = prev.scheduled_for
    if clear_schedule:
        new_schedule = None
    elif scheduled_for is not None:
        new_schedule = scheduled_for if scheduled_for.tzinfo else scheduled_for.replace(tzinfo=UTC)
    updated = Draft(
        id=prev.id,
        channel=prev.channel,
        title=title if title is not None else prev.title,
        body=body if body is not None else prev.body,
        status=status if status is not None else prev.status,
        writer=prev.writer,
        source=prev.source,
        scheduled_for=new_schedule,
        created_at=prev.created_at,
        updated_at=_utcnow(),
    )
    return write_draft(updated, poles_root=poles_root)


def set_status(draft_id: str, status: DraftStatus, *, poles_root: Path = POLES_DIR) -> Draft | None:
    """Change le statut d'un draft (valider / rejeter / publié)."""
    return _mutate(draft_id, status=status, poles_root=poles_root)


def schedule_draft(
    draft_id: str, scheduled_for: datetime | None, *, poles_root: Path = POLES_DIR
) -> Draft | None:
    """Planifie (ou déplanifie si ``None``) un draft — calendrier drag-and-drop."""
    if scheduled_for is None:
        return _mutate(draft_id, clear_schedule=True, poles_root=poles_root)
    return _mutate(draft_id, scheduled_for=scheduled_for, poles_root=poles_root)


def edit_draft(
    draft_id: str,
    *,
    title: str | None = None,
    body: str | None = None,
    poles_root: Path = POLES_DIR,
) -> Draft | None:
    """Édite le titre / corps d'un draft (validation inline du cockpit)."""
    return _mutate(draft_id, title=title, body=body, poles_root=poles_root)


def find_publishable(now: datetime, *, poles_root: Path = POLES_DIR) -> list[Draft]:
    """Drafts ``validated`` dont ``scheduled_for`` est échu (ContentBot)."""
    out: list[Draft] = []
    for draft in load_drafts(poles_root=poles_root):
        if draft.status != "validated" or draft.scheduled_for is None:
            continue
        if draft.scheduled_for <= now:
            out.append(draft)
    out.sort(key=lambda d: d.scheduled_for or now)
    return out


def mark_published(draft_id: str, *, poles_root: Path = POLES_DIR) -> Draft | None:
    return _mutate(draft_id, status="published", poles_root=poles_root)


__all__ = [
    "DRAFT_STATUSES",
    "Draft",
    "DraftStatus",
    "create_draft",
    "drafts_dir",
    "edit_draft",
    "find_publishable",
    "load_draft",
    "load_drafts",
    "make_draft_id",
    "mark_published",
    "schedule_draft",
    "set_status",
    "slugify",
    "write_draft",
]
