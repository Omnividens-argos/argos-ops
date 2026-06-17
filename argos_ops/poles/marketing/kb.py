"""KB éditoriale **éditable** du pôle Marketing (archi v2, S2).

Petite base de connaissances de marque (messages clés, preuves, FAQ, éléments
de langage) que le fondateur édite depuis le cockpit et que les skills writers
chargent comme contexte. Stockée en fichiers markdown
``data/poles/marketing/kb/<slug>.md`` (frontmatter + corps).

Distincte de la KB produit RAG (``kb-rag`` P6, pgvector) : ici c'est une KB
*éditoriale* légère, 100 % fichiers, sans embeddings (D-017).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from loguru import logger

from argos_ops.poles.config import POLES_DIR
from argos_ops.poles.marketing.drafts import slugify
from argos_ops.poles.marketing.store import read_markdown, write_markdown

KB_DIRNAME = "kb"
MARKETING_POLE = "marketing"


def _utcnow() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True)
class KBEntry:
    """Une fiche de KB éditoriale."""

    slug: str
    title: str
    body: str
    tags: tuple[str, ...] = ()
    updated_at: datetime = field(default_factory=_utcnow)


def kb_dir(*, poles_root: Path = POLES_DIR) -> Path:
    return poles_root / MARKETING_POLE / KB_DIRNAME


def _kb_path(slug: str, *, poles_root: Path) -> Path:
    return kb_dir(poles_root=poles_root) / f"{slug}.md"


def _parse_dt(value: object) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    try:
        dt = datetime.fromisoformat(str(value))
        return dt if dt.tzinfo else dt.replace(tzinfo=UTC)
    except (ValueError, TypeError):
        return _utcnow()


def _entry_from_file(path: Path) -> KBEntry:
    fm, body = read_markdown(path)
    raw_tags = fm.get("tags") or []
    tags = tuple(str(t) for t in raw_tags) if isinstance(raw_tags, list) else ()
    return KBEntry(
        slug=str(fm.get("slug") or path.stem),
        title=str(fm.get("title") or path.stem),
        body=body.strip(),
        tags=tags,
        updated_at=_parse_dt(fm.get("updated_at")),
    )


def load_kb(*, poles_root: Path = POLES_DIR) -> list[KBEntry]:
    """Toutes les fiches KB (ordre alphabétique de slug). Best-effort."""
    d = kb_dir(poles_root=poles_root)
    if not d.exists():
        return []
    out: list[KBEntry] = []
    for path in sorted(d.glob("*.md")):
        try:
            out.append(_entry_from_file(path))
        except Exception as exc:  # best-effort
            logger.warning(f"kb — fiche illisible {path} : {type(exc).__name__}: {exc}")
    return out


def load_kb_entry(slug: str, *, poles_root: Path = POLES_DIR) -> KBEntry | None:
    path = _kb_path(slug, poles_root=poles_root)
    if not path.exists():
        return None
    return _entry_from_file(path)


def upsert_kb_entry(
    *,
    title: str,
    body: str,
    slug: str | None = None,
    tags: tuple[str, ...] = (),
    poles_root: Path = POLES_DIR,
) -> KBEntry:
    """Crée ou met à jour une fiche KB. ``slug`` dérivé du titre si absent."""
    entry = KBEntry(
        slug=slug or slugify(title),
        title=title,
        body=body,
        tags=tags,
        updated_at=_utcnow(),
    )
    fm: dict[str, object] = {
        "slug": entry.slug,
        "title": entry.title,
        "tags": list(entry.tags),
        "updated_at": entry.updated_at.isoformat(),
    }
    write_markdown(_kb_path(entry.slug, poles_root=poles_root), fm, entry.body)
    logger.debug(f"kb upsert — {entry.slug}")
    return entry


def delete_kb_entry(slug: str, *, poles_root: Path = POLES_DIR) -> bool:
    """Supprime une fiche KB. ``True`` si elle existait."""
    path = _kb_path(slug, poles_root=poles_root)
    if not path.exists():
        return False
    path.unlink()
    logger.debug(f"kb delete — {slug}")
    return True


__all__ = [
    "KBEntry",
    "delete_kb_entry",
    "kb_dir",
    "load_kb",
    "load_kb_entry",
    "upsert_kb_entry",
]
