"""``AdrWriterScript`` — drafte les ADR en attente (archi v2, S8).

Lit la file ``data/poles/sre/adr/queue/<slug>.yaml`` (sous ``poles_root``) et
écrit chaque ADR au format MADR dans ``docs/adr/ADR-NNNN-<slug>.md``. Idempotent
**par slug** : un slug déjà présent réutilise son numéro (mise à jour en place),
sinon le prochain numéro libre est attribué. Générateur : vert si tout est écrit,
jaune si au moins un draft est invalide (champ requis manquant).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

import yaml
from loguru import logger

from argos_ops.config import REPO_ROOT
from argos_ops.poles.config import POLES_DIR
from argos_ops.poles.sre.base import BaseSreScript
from argos_ops.poles.sre.report import SreReport

QUEUE_SUBDIR = ("adr", "queue")
DEFAULT_ADR_DIR = REPO_ROOT / "docs" / "adr"
VALID_STATUSES = frozenset({"proposed", "accepted", "superseded"})
REQUIRED_FIELDS = ("title", "context", "decision", "consequences")
_ADR_FILE_RE = re.compile(r"^ADR-(\d{4})-(.+)\.md$")


def queue_dir(*, poles_root: Path = POLES_DIR) -> Path:
    return poles_root / "sre" / QUEUE_SUBDIR[0] / QUEUE_SUBDIR[1]


@dataclass(frozen=True)
class AdrResult:
    """Résultat de génération d'un ADR depuis la file."""

    slug: str
    ok: bool
    number: int | None
    written_to: str | None
    created: bool
    error: str | None


def slugify(text: str) -> str:
    slug = re.sub(r"[^\w\s-]", "", text.strip().lower())
    return re.sub(r"\s+", "-", slug).strip("-")


def _existing_numbers(adr_dir: Path) -> dict[str, int]:
    """Map slug → numéro pour les ADR déjà écrits."""
    out: dict[str, int] = {}
    if not adr_dir.exists():
        return out
    for path in adr_dir.glob("ADR-*.md"):
        m = _ADR_FILE_RE.match(path.name)
        if m:
            out[m.group(2)] = int(m.group(1))
    return out


def _parse_date(value: object) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except (ValueError, TypeError):
        return date(1970, 1, 1)


def render_adr(draft: dict[str, object], *, number: int) -> str:
    """Rend un ADR MADR. Lève ``ValueError`` si un champ requis manque."""
    for field in REQUIRED_FIELDS:
        if not str(draft.get(field, "")).strip():
            raise ValueError(f"champ requis manquant : {field}")
    status = str(draft.get("status", "proposed"))
    if status not in VALID_STATUSES:
        raise ValueError(f"statut invalide : {status}")
    decided = _parse_date(draft.get("decided_on"))
    return (
        f"# ADR-{number:04d} — {draft['title']}\n\n"
        f"- Statut : **{status}**\n"
        f"- Date : {decided.isoformat()}\n\n"
        f"## Contexte\n\n{str(draft['context']).strip()}\n\n"
        f"## Décision\n\n{str(draft['decision']).strip()}\n\n"
        f"## Conséquences\n\n{str(draft['consequences']).strip()}\n"
    )


def generate_all(*, poles_root: Path, adr_dir: Path) -> list[AdrResult]:
    """Draft chaque ADR de la file. Numérotation idempotente par slug."""
    src = queue_dir(poles_root=poles_root)
    if not src.exists():
        return []
    numbers = _existing_numbers(adr_dir)
    next_number = (max(numbers.values()) + 1) if numbers else 1
    results: list[AdrResult] = []
    for path in sorted(src.glob("*.yaml")):
        slug = path.stem
        try:
            raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            if not isinstance(raw, dict):
                raise ValueError("draft racine doit être un mapping")
            slug = slugify(str(raw.get("slug") or slug))
            existing = slug in numbers
            number = numbers.get(slug, next_number)
            markdown = render_adr(raw, number=number)
        except (yaml.YAMLError, ValueError) as exc:
            logger.warning(f"adr_writer — draft '{slug}' invalide : {exc}")
            results.append(AdrResult(slug, False, None, None, False, str(exc)))
            continue
        if not existing:
            numbers[slug] = number
            next_number = max(numbers.values()) + 1
        adr_dir.mkdir(parents=True, exist_ok=True)
        out_path = adr_dir / f"ADR-{number:04d}-{slug}.md"
        out_path.write_text(markdown, encoding="utf-8")
        results.append(AdrResult(slug, True, number, str(out_path), not existing, None))
    return results


def build_report(results: list[AdrResult]) -> SreReport:
    if not results:
        return SreReport("green", "Aucun ADR en attente dans la file.")
    n_ok = sum(1 for r in results if r.ok)
    n_created = sum(1 for r in results if r.created)
    n_bad = len(results) - n_ok
    summary = f"{n_ok} ADR écrit(s) ({n_created} nouveau(x)) · {n_bad} draft(s) invalide(s)"
    detail = "\n".join(f"- {r.slug} : {r.error}" for r in results if not r.ok)
    return SreReport("yellow" if n_bad else "green", summary, detail)


class AdrWriterScript(BaseSreScript):
    """Drafte les ADR en attente au format MADR."""

    name = "adr_writer"

    def __init__(self, *, poles_root: Path = POLES_DIR, adr_dir: Path | None = None) -> None:
        super().__init__(poles_root=poles_root)
        self._adr_dir = adr_dir or DEFAULT_ADR_DIR

    async def check(self) -> SreReport:
        return build_report(generate_all(poles_root=self.poles_root, adr_dir=self._adr_dir))


__all__ = [
    "REQUIRED_FIELDS",
    "VALID_STATUSES",
    "AdrResult",
    "AdrWriterScript",
    "build_report",
    "generate_all",
    "queue_dir",
    "render_adr",
    "slugify",
]
