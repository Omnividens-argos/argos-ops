"""Lecture de l'historique git pour ChangelogBot + ReleaseNotesBot (P22.G).

Subprocess ``git log`` uniquement — pas de PyGithub, pas de gh API
authentifiée. On extrait les conventional commits :

    feat(scope): description (#PR)
    fix(scope): description
    chore: ...
    refactor: ...
    docs: ...

Tout commit qui ne match pas le préfixe est rangé en ``other``.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass

# Préfixes conventional commits supportés
COMMIT_TYPES: tuple[str, ...] = ("feat", "fix", "chore", "refactor", "docs", "test", "perf")

# Regex parsing : type(scope?): description
_COMMIT_RE = re.compile(
    r"^(?P<type>" + "|".join(COMMIT_TYPES) + r")(?:\((?P<scope>[^)]+)\))?(?P<bang>!?):\s+(?P<desc>.+)$"
)


@dataclass(frozen=True)
class Commit:
    """Un commit conventional parsé."""

    sha: str
    type: str  # feat | fix | chore | refactor | docs | test | perf | other
    scope: str | None
    description: str
    breaking: bool
    raw_subject: str


def run_git(args: list[str]) -> str:
    """Exécute ``git <args>`` et retourne stdout (str). Lève sur exit != 0."""
    result = subprocess.run(
        ["git", *args],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return result.stdout


def list_commits(*, from_ref: str | None, to_ref: str = "HEAD") -> list[Commit]:
    """Liste les commits ``from_ref..to_ref`` (exclusif from, inclusif to).

    Si ``from_ref`` est None, retourne les 100 derniers commits (cap large
    pour éviter de spammer un repo récent).
    """
    range_arg = f"-n100 {to_ref}" if from_ref is None else f"{from_ref}..{to_ref}"
    raw = run_git(["log", "--pretty=format:%H%x09%s", *range_arg.split()])
    commits: list[Commit] = []
    for line in raw.splitlines():
        if not line.strip():
            continue
        sha, _, subject = line.partition("\t")
        commits.append(_parse_commit(sha, subject))
    return commits


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


def group_by_type(commits: list[Commit]) -> dict[str, list[Commit]]:
    """Regroupe les commits par type, dans l'ordre des sections changelog.

    Ordre : feat (highlights) > fix > perf > refactor > docs > test > chore > other.
    """
    order = ("feat", "fix", "perf", "refactor", "docs", "test", "chore", "other")
    out: dict[str, list[Commit]] = {key: [] for key in order}
    for commit in commits:
        bucket = commit.type if commit.type in out else "other"
        out[bucket].append(commit)
    return {key: lst for key, lst in out.items() if lst}


def list_tags() -> list[str]:
    """Retourne la liste des tags git triés par date de création desc."""
    raw = run_git(["tag", "--sort=-creatordate"])
    return [line for line in raw.splitlines() if line.strip()]


__all__ = [
    "COMMIT_TYPES",
    "Commit",
    "group_by_type",
    "list_commits",
    "list_tags",
    "run_git",
]
