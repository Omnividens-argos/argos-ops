"""ADRWriter — Tech Lead (Sprint 13).

Drafte un ADR (Architecture Decision Record) à partir d'un input
markdown structuré et l'écrit dans ``docs/adr/ADR-NNNN-<slug>.md``.

Format ADR — MADR léger (cf. https://adr.github.io/madr/) :
- Titre
- Statut (proposed / accepted / superseded)
- Date
- Contexte
- Décision
- Conséquences

Numérotation : auto-incrémente depuis le dossier ``docs/adr/`` (ADR-0001,
ADR-0002, …). Idempotent à condition de fournir un ``slug`` stable : si
un ADR avec le même slug existe déjà, on le met à jour plutôt que d'en
créer un doublon.

Pas de slash watcher — c'est un générateur invoqué via ``/write-adr <slug>``
ou par d'autres bots (ex : DecisionLogger Sprint 9 quand il sortira).
Pas d'appel API GitHub — l'input peut venir d'une PR mais c'est au
founder de la coller.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Literal

from loguru import logger

from argos_ops.agents.base import BaseAgent, RunResult
from argos_ops.config import REPO_ROOT

DEFAULT_ADR_DIR: Path = REPO_ROOT / "docs" / "adr"
ADRStatus = Literal["proposed", "accepted", "superseded"]
VALID_STATUSES: frozenset[str] = frozenset({"proposed", "accepted", "superseded"})

_ADR_FILE_RE = re.compile(r"^ADR-(\d{4})-(.+)\.md$")


@dataclass(frozen=True)
class ADRDraft:
    """Contenu d'un ADR à écrire."""

    slug: str
    title: str
    status: ADRStatus
    context: str
    decision: str
    consequences: str
    decided_on: date


def _slugify(text: str) -> str:
    """Slugify simple — alphanum + tirets, minuscule."""
    cleaned = re.sub(r"[^\w\s-]", "", text.lower(), flags=re.UNICODE)
    cleaned = re.sub(r"\s+", "-", cleaned.strip())
    cleaned = re.sub(r"-+", "-", cleaned)
    return cleaned.strip("-") or "adr"


def next_adr_number(adr_dir: Path) -> int:
    """Renvoie le prochain numéro ADR libre (1 si dossier vide)."""
    if not adr_dir.exists():
        return 1
    max_num = 0
    for entry in adr_dir.iterdir():
        m = _ADR_FILE_RE.match(entry.name)
        if m:
            max_num = max(max_num, int(m.group(1)))
    return max_num + 1


def find_existing_adr(adr_dir: Path, slug: str) -> Path | None:
    """Cherche un ADR existant avec ce slug (idempotence)."""
    if not adr_dir.exists():
        return None
    for entry in adr_dir.iterdir():
        m = _ADR_FILE_RE.match(entry.name)
        if m and m.group(2) == slug:
            return entry
    return None


def render_adr(draft: ADRDraft, *, number: int) -> str:
    """Format ADR markdown — frontmatter minimal + sections MADR."""
    return "\n".join(
        [
            f"# ADR-{number:04d} — {draft.title}",
            "",
            f"- **Statut :** {draft.status}",
            f"- **Date :** {draft.decided_on.isoformat()}",
            "",
            "## Contexte",
            "",
            draft.context.strip(),
            "",
            "## Décision",
            "",
            draft.decision.strip(),
            "",
            "## Conséquences",
            "",
            draft.consequences.strip(),
            "",
        ]
    )


def write_adr(
    draft: ADRDraft, *, adr_dir: Path = DEFAULT_ADR_DIR
) -> tuple[Path, int, bool]:
    """Écrit le markdown. Retourne (path, number, created).

    Si un ADR existant a le même slug, on le met à jour en gardant son
    numéro. Sinon on incrémente.
    """
    adr_dir.mkdir(parents=True, exist_ok=True)
    existing = find_existing_adr(adr_dir, draft.slug)
    if existing is not None:
        m = _ADR_FILE_RE.match(existing.name)
        assert m is not None
        number = int(m.group(1))
        existing.write_text(render_adr(draft, number=number), encoding="utf-8")
        return existing, number, False

    number = next_adr_number(adr_dir)
    target = adr_dir / f"ADR-{number:04d}-{draft.slug}.md"
    target.write_text(render_adr(draft, number=number), encoding="utf-8")
    return target, number, True


def build_draft(
    *,
    title: str,
    context: str,
    decision: str,
    consequences: str,
    status: str = "proposed",
    slug: str | None = None,
    decided_on: date | None = None,
) -> ADRDraft:
    """Construit un draft validé (status + slug normalisés)."""
    if status not in VALID_STATUSES:
        raise ValueError(
            f"status invalide : {status!r} (attendu : {sorted(VALID_STATUSES)})"
        )
    return ADRDraft(
        slug=slug or _slugify(title),
        title=title.strip(),
        status=status,  # type: ignore[arg-type]
        context=context,
        decision=decision,
        consequences=consequences,
        decided_on=decided_on or datetime.now(UTC).date(),
    )


class ADRWriter(BaseAgent):
    """Tech Lead — drafte un ADR depuis un input markdown structuré."""

    name = "ADRWriter"
    command = "/write-adr"
    breaker_name = None
    ai_act_risk_class = "minimal"

    def __init__(
        self, draft: ADRDraft, *, adr_dir: Path = DEFAULT_ADR_DIR
    ) -> None:
        self._draft = draft
        self._adr_dir = adr_dir

    async def run(self) -> RunResult:
        target, number, created = write_adr(self._draft, adr_dir=self._adr_dir)
        action = "created" if created else "updated"
        logger.info(f"ADRWriter — ADR-{number:04d} {action} ({target})")
        return RunResult(
            status="success",
            output_summary=(
                f"adr=ADR-{number:04d} slug={self._draft.slug} action={action}"
            ),
            extras={"written_to": str(target), "number": number, "created": created},
        )


__all__ = [
    "DEFAULT_ADR_DIR",
    "VALID_STATUSES",
    "ADRDraft",
    "ADRStatus",
    "ADRWriter",
    "build_draft",
    "find_existing_adr",
    "next_adr_number",
    "render_adr",
    "write_adr",
]
