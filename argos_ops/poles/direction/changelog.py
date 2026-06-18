"""Changelog du pôle Direction (archi v2, S6).

Réutilise la logique pure de :mod:`argos_ops.product.git_history` (``Commit``,
``group_by_type``, ``COMMIT_TYPES``) et le rendu de
:func:`argos_ops.agents.changelog_bot.render_changelog` — **aucun re-port**. En
local-first (D-017), au lieu d'appeler ``git log`` (non déterministe, non testable
hermétiquement), on lit un **snapshot** ``data/poles/direction/changelog/commits.yaml``
que le fondateur exporte (``git log --pretty=format:%h%x09%s``).

Format du snapshot ::

    from_ref: v0.5.0          # optionnel (libellé de période)
    to_ref: HEAD
    commits:
      - sha: 836ef6e
        subject: "feat(finance): pôle Finance complet"
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from argos_ops.agents.changelog_bot import render_changelog
from argos_ops.poles.config import POLES_DIR
from argos_ops.poles.direction.store import load_yaml_mapping
from argos_ops.product.git_history import COMMIT_TYPES, Commit, group_by_type

DIRECTION_POLE = "direction"

_COMMIT_RE = re.compile(
    r"^(?P<type>"
    + "|".join(COMMIT_TYPES)
    + r")(?:\((?P<scope>[^)]+)\))?(?P<bang>!?):\s+(?P<desc>.+)$"
)


@dataclass(frozen=True)
class ChangelogView:
    """Changelog rendu + compteurs (vue cockpit + corps mémoire)."""

    period_label: str
    n_commits: int
    n_sections: int
    section_counts: tuple[tuple[str, int], ...]
    markdown: str


def changelog_path(*, poles_root: Path = POLES_DIR) -> Path:
    return poles_root / DIRECTION_POLE / "changelog" / "commits.yaml"


def _parse_commit(sha: str, subject: str) -> Commit:
    match = _COMMIT_RE.match(subject)
    if match is None:
        return Commit(
            sha=sha[:7],
            type="other",
            scope=None,
            description=subject,
            breaking=False,
            raw_subject=subject,
        )
    return Commit(
        sha=sha[:7],
        type=match.group("type"),
        scope=match.group("scope"),
        description=match.group("desc"),
        breaking=match.group("bang") == "!",
        raw_subject=subject,
    )


def load_commits(*, poles_root: Path = POLES_DIR) -> list[Commit]:
    """Lit le snapshot de commits (vide si absent / mal typé)."""
    raw = load_yaml_mapping(changelog_path(poles_root=poles_root))
    rows = raw.get("commits")
    if not isinstance(rows, list):
        return []
    commits: list[Commit] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        subject = str(row.get("subject") or "").strip()
        if not subject:
            continue
        commits.append(_parse_commit(str(row.get("sha") or ""), subject))
    return commits


def build_changelog(*, poles_root: Path = POLES_DIR) -> ChangelogView:
    """Construit le changelog markdown groupé par type conventional commit."""
    raw = load_yaml_mapping(changelog_path(poles_root=poles_root))
    commits = load_commits(poles_root=poles_root)
    from_ref = str(raw.get("from_ref")) if raw.get("from_ref") else None
    to_ref = str(raw.get("to_ref") or "HEAD")
    sections = group_by_type(commits)
    period_label = f"{from_ref} → {to_ref}" if from_ref else f"derniers commits → {to_ref}"
    markdown = render_changelog(
        period_label=period_label, from_ref=from_ref, to_ref=to_ref, sections=sections
    )
    return ChangelogView(
        period_label=period_label,
        n_commits=len(commits),
        n_sections=len(sections),
        section_counts=tuple((k, len(v)) for k, v in sections.items()),
        markdown=markdown,
    )


__all__ = ["ChangelogView", "build_changelog", "changelog_path", "load_commits"]
