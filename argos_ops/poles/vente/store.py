"""Helpers de (dé)sérialisation **frontmatter** pour les assets du pôle Vente.

Les leads enrichis, drafts de réponse, brouillons de RDV et devis/contrats sont
stockés en fichiers markdown ``---\\nyaml\\n---\\n\\ncorps`` — même idiome maison
que la mémoire de pôle (:mod:`argos_ops.poles.memory`) et que les stores des
pôles Marketing / Pub. Centralisé ici pour ne pas dupliquer le parsing et garder
le pôle Vente autonome (pas de dépendance de code vers un autre pôle).

Local-first (D-017) : aucune valeur secrète ici (faits métier publics), ``loguru``
only, lecture **best-effort** (un fichier illisible est ignoré par l'appelant).
"""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

import yaml


def parse_date(value: object) -> date:
    """Parse une valeur YAML (``date`` / ``datetime`` / str ISO) en ``date``.

    ``datetime`` est testé **avant** ``date`` (datetime hérite de date) pour ne
    jamais renvoyer un ``datetime`` là où un ``date`` est attendu. Centralisé ici
    (réutilisé par pipeline / proposals / inbox) pour ne pas dupliquer le parsing.
    """
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


def split_frontmatter(content: str) -> tuple[dict[str, object], str]:
    """Sépare le frontmatter YAML du corps markdown. ``({}, content)`` si absent."""
    if not content.startswith("---\n"):
        return {}, content
    end = content.find("\n---", 4)
    if end == -1:
        return {}, content
    fm = yaml.safe_load(content[4:end]) or {}
    body = content[end + 5 :]
    return (fm if isinstance(fm, dict) else {}), body


def join_frontmatter(fm: dict[str, object], body: str) -> str:
    """Sérialise ``fm`` + ``body`` en markdown avec frontmatter YAML."""
    front = yaml.safe_dump(fm, sort_keys=False, allow_unicode=True)
    return f"---\n{front}---\n\n{body.strip()}\n"


def read_markdown(path: Path) -> tuple[dict[str, object], str]:
    """Lit un fichier markdown → (frontmatter, corps)."""
    return split_frontmatter(path.read_text(encoding="utf-8"))


def write_markdown(path: Path, fm: dict[str, object], body: str) -> None:
    """Écrit (frontmatter, corps) dans un fichier markdown (crée le dossier)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(join_frontmatter(fm, body), encoding="utf-8")


__all__ = ["join_frontmatter", "parse_date", "read_markdown", "split_frontmatter", "write_markdown"]
