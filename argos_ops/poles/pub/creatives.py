"""File de **créas** publicitaires du pôle Pub (archi v2, S3).

Une créa = un jeu de **variantes A/B/C** (angles différents) pour une plateforme,
**en attente de validation humaine** (D-017, humain-in-the-loop) avant toute mise
en ligne. Stockée en fichier markdown ``data/poles/pub/creatives/<id>.md``
(frontmatter : méta + variantes ; corps : le brief de campagne).

Cycle de vie ::

    draft ──valider──▶ validated ──(go live, shadow)──▶ live
      └────rejeter────▶ rejected

Module *pur* (fichiers only) partagé par le cockpit (validation + comparaison
A/B côte à côte) et par le script
:class:`~argos_ops.poles.pub.scripts.ad_bot.AdBotScript` (qui pousse — en shadow —
les ``validated``). La validation de longueur par variante se fait contre les
contraintes de :mod:`argos_ops.poles.pub.platforms`.
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
from argos_ops.poles.pub.store import read_markdown, write_markdown

CREATIVES_DIRNAME = "creatives"
PUB_POLE = "pub"

CreativeStatus = Literal["draft", "validated", "live", "rejected"]
CREATIVE_STATUSES: tuple[CreativeStatus, ...] = ("draft", "validated", "live", "rejected")

_SLUG_MAX = 48


def _utcnow() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True)
class Variant:
    """Une variante de créa (un angle). ``label`` = A / B / C."""

    label: str
    angle: str
    headline: str
    primary_text: str
    description: str = ""


@dataclass(frozen=True)
class Creative:
    """Un jeu de variantes A/B/C pour une plateforme, en attente de validation."""

    id: str
    platform: str
    title: str
    status: CreativeStatus = "draft"
    objective: str | None = None
    persona: str | None = None
    variants: tuple[Variant, ...] = ()
    brief: str = ""
    source: str | None = None
    created_at: datetime = field(default_factory=_utcnow)
    updated_at: datetime = field(default_factory=_utcnow)


# =============================================================================
# Identité / chemins
# =============================================================================
def slugify(text: str) -> str:
    """Slug kebab-case stable (ascii, borné). Translittère les accents."""
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    norm = re.sub(r"[^a-z0-9]+", "-", ascii_text.strip().lower()).strip("-")
    return norm[:_SLUG_MAX] or "crea"


def make_creative_id(platform: str, title: str) -> str:
    """``<plateforme>-<slug-du-titre>`` — stable et lisible."""
    return f"{platform}-{slugify(title)}"


def creatives_dir(*, poles_root: Path = POLES_DIR) -> Path:
    return poles_root / PUB_POLE / CREATIVES_DIRNAME


def _creative_path(creative_id: str, *, poles_root: Path) -> Path:
    return creatives_dir(poles_root=poles_root) / f"{creative_id}.md"


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


def _coerce_status(value: object) -> CreativeStatus:
    raw = str(value or "draft")
    return raw if raw in CREATIVE_STATUSES else "draft"


def _variants_from_fm(value: object) -> tuple[Variant, ...]:
    if not isinstance(value, list):
        return ()
    out: list[Variant] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        out.append(
            Variant(
                label=str(item.get("label") or "?"),
                angle=str(item.get("angle") or ""),
                headline=str(item.get("headline") or ""),
                primary_text=str(item.get("primary_text") or ""),
                description=str(item.get("description") or ""),
            )
        )
    return tuple(out)


def _variants_to_fm(variants: tuple[Variant, ...]) -> list[dict[str, str]]:
    return [
        {
            "label": v.label,
            "angle": v.angle,
            "headline": v.headline,
            "primary_text": v.primary_text,
            "description": v.description,
        }
        for v in variants
    ]


def _creative_to_fm(creative: Creative) -> dict[str, object]:
    return {
        "id": creative.id,
        "platform": creative.platform,
        "title": creative.title,
        "status": creative.status,
        "objective": creative.objective,
        "persona": creative.persona,
        "source": creative.source,
        "created_at": creative.created_at.isoformat(),
        "updated_at": creative.updated_at.isoformat(),
        "variants": _variants_to_fm(creative.variants),
    }


def _read_creative_file(path: Path) -> Creative:
    fm, body = read_markdown(path)
    created = _parse_dt(fm.get("created_at")) or _utcnow()
    updated = _parse_dt(fm.get("updated_at")) or created
    return Creative(
        id=str(fm.get("id") or path.stem),
        platform=str(fm.get("platform") or "google_search"),
        title=str(fm.get("title") or ""),
        status=_coerce_status(fm.get("status")),
        objective=(str(fm["objective"]) if fm.get("objective") else None),
        persona=(str(fm["persona"]) if fm.get("persona") else None),
        variants=_variants_from_fm(fm.get("variants")),
        brief=body.strip(),
        source=(str(fm["source"]) if fm.get("source") else None),
        created_at=created,
        updated_at=updated,
    )


# =============================================================================
# Lecture
# =============================================================================
def load_creatives(*, poles_root: Path = POLES_DIR) -> list[Creative]:
    """Toutes les créas (du plus récent au plus ancien). Best-effort."""
    d = creatives_dir(poles_root=poles_root)
    if not d.exists():
        return []
    out: list[Creative] = []
    for path in d.glob("*.md"):
        try:
            out.append(_read_creative_file(path))
        except Exception as exc:  # best-effort, comme la mémoire
            logger.warning(f"creatives — fichier illisible {path} : {type(exc).__name__}: {exc}")
    out.sort(key=lambda c: c.created_at, reverse=True)
    return out


def load_creative(creative_id: str, *, poles_root: Path = POLES_DIR) -> Creative | None:
    path = _creative_path(creative_id, poles_root=poles_root)
    if not path.exists():
        return None
    return _read_creative_file(path)


# =============================================================================
# Écriture / mutations
# =============================================================================
def write_creative(creative: Creative, *, poles_root: Path = POLES_DIR) -> Creative:
    """Persiste une créa (crée le dossier). Bas niveau."""
    write_markdown(
        _creative_path(creative.id, poles_root=poles_root),
        _creative_to_fm(creative),
        creative.brief,
    )
    logger.debug(f"creative write — {creative.id} ({creative.status})")
    return creative


def create_creative(
    *,
    platform: str,
    title: str,
    variants: tuple[Variant, ...] = (),
    objective: str | None = None,
    persona: str | None = None,
    brief: str = "",
    source: str | None = None,
    poles_root: Path = POLES_DIR,
) -> Creative:
    """Crée (ou écrase) une créa ``status=draft``."""
    creative = Creative(
        id=make_creative_id(platform, title),
        platform=platform,
        title=title,
        status="draft",
        objective=objective,
        persona=persona,
        variants=variants,
        brief=brief,
        source=source,
    )
    return write_creative(creative, poles_root=poles_root)


def set_status(
    creative_id: str, status: CreativeStatus, *, poles_root: Path = POLES_DIR
) -> Creative | None:
    """Change le statut d'une créa (valider / rejeter / live)."""
    prev = load_creative(creative_id, poles_root=poles_root)
    if prev is None:
        logger.warning(f"creative set_status — introuvable : {creative_id}")
        return None
    updated = Creative(
        id=prev.id,
        platform=prev.platform,
        title=prev.title,
        status=status,
        objective=prev.objective,
        persona=prev.persona,
        variants=prev.variants,
        brief=prev.brief,
        source=prev.source,
        created_at=prev.created_at,
        updated_at=_utcnow(),
    )
    return write_creative(updated, poles_root=poles_root)


def find_publishable(*, poles_root: Path = POLES_DIR) -> list[Creative]:
    """Créas ``validated`` prêtes à être poussées (shadow) par ``ad_bot``."""
    return [c for c in load_creatives(poles_root=poles_root) if c.status == "validated"]


__all__ = [
    "CREATIVE_STATUSES",
    "Creative",
    "CreativeStatus",
    "Variant",
    "create_creative",
    "creatives_dir",
    "find_publishable",
    "load_creative",
    "load_creatives",
    "make_creative_id",
    "set_status",
    "slugify",
    "write_creative",
]
