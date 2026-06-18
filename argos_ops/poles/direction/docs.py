"""Génération de documents du pôle Direction (archi v2, S6).

Produit les livrables de pilotage dans ``data/poles/direction/docs/`` et tente un
rendu PDF (preview) via :func:`argos_ops.sales.templates.try_render_pdf` (pandoc
si dispo, sinon Markdown seul — D-009) :

- **board pack** mensuel (interne) — :mod:`argos_ops.poles.direction.board` ;
- **roadmap publique** — :mod:`argos_ops.poles.direction.roadmap` ;
- **changelog** — :mod:`argos_ops.poles.direction.changelog` ;
- **release notes** user-friendly dérivées du changelog (skill ``release-notes``).

Les trois derniers sont des **artefacts publics** : leur génération est soumise au
garde-fou :func:`argos_ops.poles.direction.release.release_blocking` — appliqué par
l'appelant (API / agent), pas ici (ce module ne fait que rendre). Lecture markdown
restreinte aux enfants directs de ``docs/`` (anti-traversal). Aucune valeur secrète.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Literal

from loguru import logger

from argos_ops.poles.config import POLES_DIR
from argos_ops.poles.direction import board, changelog, roadmap
from argos_ops.poles.direction.fleet import FleetSnapshot
from argos_ops.product.git_history import group_by_type
from argos_ops.sales.templates import try_render_pdf

DIRECTION_POLE = "direction"
DocKind = Literal["board", "roadmap", "changelog", "release_notes", "other"]

_SECTION_TITLES: dict[str, str] = {
    "feat": "✨ Nouveautés",
    "fix": "🐛 Corrections",
    "perf": "⚡ Performance",
}


def docs_dir(*, poles_root: Path = POLES_DIR) -> Path:
    return poles_root / DIRECTION_POLE / "docs"


@dataclass(frozen=True)
class DocEntry:
    """Un document généré + son statut PDF."""

    name: str
    kind: DocKind
    has_pdf: bool


def _classify(stem: str) -> DocKind:
    if stem.startswith("board"):
        return "board"
    if stem.startswith("roadmap"):
        return "roadmap"
    if stem.startswith("release_notes") or stem.startswith("release-notes"):
        return "release_notes"
    if stem.startswith("changelog"):
        return "changelog"
    return "other"


def list_docs(*, poles_root: Path = POLES_DIR) -> list[DocEntry]:
    """Liste les docs markdown générés. Best-effort."""
    d = docs_dir(poles_root=poles_root)
    if not d.exists():
        return []
    return [
        DocEntry(name=p.name, kind=_classify(p.stem), has_pdf=p.with_suffix(".pdf").exists())
        for p in sorted(d.glob("*.md"))
    ]


def read_doc(name: str, *, poles_root: Path = POLES_DIR) -> str | None:
    """Contenu markdown d'un doc (preview). ``None`` si absent / hors ``docs/``."""
    base = docs_dir(poles_root=poles_root).resolve()
    path = (base / name).resolve()
    if path.parent != base or path.suffix != ".md" or not path.exists():
        return None
    return path.read_text(encoding="utf-8")


def _write_with_pdf(name: str, markdown: str, *, poles_root: Path) -> Path:
    d = docs_dir(poles_root=poles_root)
    d.mkdir(parents=True, exist_ok=True)
    md_path = d / name
    md_path.write_text(markdown, encoding="utf-8")
    if not try_render_pdf(md_path, pdf_path=md_path.with_suffix(".pdf")):
        logger.debug(f"direction/docs — pandoc absent, {name} en Markdown seul (D-009)")
    return md_path


def generate_board(
    snapshot: FleetSnapshot, *, poles_root: Path = POLES_DIR, today: date | None = None
) -> Path:
    """Génère le board pack mensuel (interne)."""
    today = today or date.today()
    metrics = board.build_metrics(snapshot, poles_root=poles_root, today=today)
    return _write_with_pdf(
        f"board_{metrics.period}.md", board.render(metrics), poles_root=poles_root
    )


def generate_roadmap(*, poles_root: Path = POLES_DIR) -> Path:
    """Génère la roadmap publique (codes sprint retirés)."""
    view = roadmap.build_roadmap(poles_root=poles_root)
    return _write_with_pdf("roadmap.md", view.markdown, poles_root=poles_root)


def generate_changelog(*, poles_root: Path = POLES_DIR) -> Path:
    """Génère le changelog depuis le snapshot de commits."""
    view = changelog.build_changelog(poles_root=poles_root)
    return _write_with_pdf("changelog.md", view.markdown, poles_root=poles_root)


def _render_release_notes(poles_root: Path, today: date) -> str:
    """Notes de version user-friendly dérivées des commits (feat / fix / perf)."""
    commits = changelog.load_commits(poles_root=poles_root)
    sections = group_by_type(commits)
    parts = [
        f"# Notes de version Argos — {today.isoformat()}\n",
        "> Nouveautés et améliorations de la plateforme Argos. "
        "Rédigé pour nos clients — sans jargon interne.\n",
    ]
    for key, title in _SECTION_TITLES.items():
        rows = sections.get(key, [])
        if not rows:
            continue
        parts.append(f"\n## {title}\n")
        for c in rows:
            parts.append(f"- {c.description}")
    if not any(sections.get(k) for k in _SECTION_TITLES):
        parts.append("\n_Aucune nouveauté notable sur cette période._\n")
    return "\n".join(parts) + "\n"


def generate_release_notes(*, poles_root: Path = POLES_DIR, today: date | None = None) -> Path:
    """Génère les notes de version (skill ``release-notes``)."""
    today = today or date.today()
    return _write_with_pdf(
        f"release_notes_{today.isoformat()}.md",
        _render_release_notes(poles_root, today),
        poles_root=poles_root,
    )


__all__ = [
    "DocEntry",
    "DocKind",
    "docs_dir",
    "generate_board",
    "generate_changelog",
    "generate_release_notes",
    "generate_roadmap",
    "list_docs",
    "read_doc",
]
