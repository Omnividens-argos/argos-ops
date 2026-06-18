"""Helpers de (dé)sérialisation **frontmatter** + YAML pour le pôle Direction.

Mêmes idiomes maison que la mémoire de pôle (:mod:`argos_ops.poles.memory`) et
que les stores Vente / Finance : fichiers markdown ``---\\nyaml\\n---\\n\\ncorps``
pour les docs, mappings YAML pour les snapshots. Centralisé ici pour ne pas
dupliquer le parsing et garder le pôle Direction **autonome** (pas de dépendance
de code vers un autre pôle).

Local-first (D-017) : aucune valeur secrète ici (faits métier), ``loguru`` only,
lecture **best-effort** (un fichier illisible est ignoré par l'appelant).
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date, datetime
from pathlib import Path

import yaml


def parse_date(value: object) -> date:
    """Parse une valeur YAML (``date`` / ``datetime`` / str ISO) en ``date``.

    ``datetime`` est testé **avant** ``date`` (datetime hérite de date) pour ne
    jamais renvoyer un ``datetime`` là où un ``date`` est attendu.
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


def load_yaml_mapping(path: Path) -> dict[str, object]:
    """Charge un fichier YAML en mapping. ``{}`` si absent / vide / non-mapping."""
    if not path.exists():
        return {}
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return raw if isinstance(raw, dict) else {}


def dump_yaml_mapping(path: Path, data: Mapping[str, object]) -> None:
    """Écrit un mapping YAML (crée le dossier). Ordre des clés préservé."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(dict(data), sort_keys=False, allow_unicode=True), encoding="utf-8"
    )


__all__ = [
    "dump_yaml_mapping",
    "join_frontmatter",
    "load_yaml_mapping",
    "parse_date",
    "read_markdown",
    "split_frontmatter",
    "write_markdown",
]
