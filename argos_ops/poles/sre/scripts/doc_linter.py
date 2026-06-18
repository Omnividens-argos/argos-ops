"""``DocLinterScript`` — liens internes morts dans la doc (archi v2, S8).

Scanne ``docs/**/*.md`` + ``README.md`` + ``CLAUDE.md`` (sous ``root``, REPO_ROOT
par défaut) et vérifie chaque lien markdown **interne** :

- la cible fichier existe-t-elle (sinon ``missing_file`` → rouge) ?
- l'ancre ``#slug`` correspond-elle à un titre de la cible (sinon ``missing_anchor``
  → jaune, titre renommé) ?

Les liens externes (http/https/mailto/tel) et les ancres pures vers le même
fichier sont vérifiés ; les images ``![...]`` sont ignorées. Pur filesystem.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from argos_ops.config import REPO_ROOT
from argos_ops.poles.config import POLES_DIR
from argos_ops.poles.sre.base import BaseSreScript
from argos_ops.poles.sre.report import Severity, SreReport, worst

DOC_GLOBS = ("docs/**/*.md", "README.md", "CLAUDE.md")
# Liens markdown [texte](cible) hors images (pas précédé de '!').
_LINK_RE = re.compile(r"(?<!!)\[([^\]]+)\]\(([^)]+)\)")
_HEADING_RE = re.compile(r"^#{1,6}\s+(.+?)\s*#*\s*$", re.MULTILINE)
_EXTERNAL = ("http://", "https://", "mailto:", "tel:", "//")


@dataclass(frozen=True)
class LinkIssue:
    """Un lien interne cassé."""

    source_file: str
    line: int
    text: str
    target: str
    kind: str  # missing_file | missing_anchor
    detail: str


def slugify_heading(heading: str) -> str:
    """Slug d'ancre style GitHub : minuscule, ponctuation retirée, chaque espace→un tiret.

    GitHub ne **collapse pas** les espaces multiples : « D-019 : Abandon » →
    ``d-019--abandon`` (double tiret là où le « : » a laissé deux espaces).
    """
    slug = heading.strip().lower()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"\s", "-", slug)
    return slug.strip("-")


def _anchors_of(text: str) -> set[str]:
    return {slugify_heading(m.group(1)) for m in _HEADING_RE.finditer(text)}


def _line_of(content: str, index: int) -> int:
    return content.count("\n", 0, index) + 1


def _split_target(target: str) -> tuple[str, str | None]:
    """Sépare ``chemin#ancre`` → (chemin, ancre|None). Garde l'ancre seule (#x)."""
    target = target.split(" ")[0].strip()  # retire le titre optionnel ("(url "title")")
    if "#" in target:
        path, _, anchor = target.partition("#")
        return path, anchor
    return target, None


def lint_file(path: Path, root: Path) -> tuple[int, list[LinkIssue]]:
    """Vérifie les liens internes d'un fichier markdown. Renvoie (n_liens, issues)."""
    content = path.read_text(encoding="utf-8")
    issues: list[LinkIssue] = []
    checked = 0
    for m in _LINK_RE.finditer(content):
        text, raw_target = m.group(1), m.group(2).strip()
        if raw_target.startswith(_EXTERNAL) or not raw_target:
            continue
        checked += 1
        rel_path, anchor = _split_target(raw_target)
        line = _line_of(content, m.start())
        # Lien d'ancre pur (#section) → cible = fichier courant.
        target_file = path if rel_path == "" else (path.parent / rel_path).resolve()
        if rel_path != "" and not target_file.exists():
            issues.append(
                LinkIssue(
                    str(path.relative_to(root)),
                    line,
                    text,
                    raw_target,
                    "missing_file",
                    f"fichier introuvable : {rel_path}",
                )
            )
            continue
        if anchor:
            try:
                target_text = target_file.read_text(encoding="utf-8")
            except OSError:
                continue
            if slugify_heading(anchor) not in _anchors_of(target_text):
                issues.append(
                    LinkIssue(
                        str(path.relative_to(root)),
                        line,
                        text,
                        raw_target,
                        "missing_anchor",
                        f"ancre introuvable : #{anchor}",
                    )
                )
    return checked, issues


def scan_docs(root: Path) -> tuple[int, int, list[LinkIssue]]:
    """Scanne tous les fichiers doc sous ``root``. Renvoie (n_fichiers, n_liens, issues)."""
    seen: set[Path] = set()
    files: list[Path] = []
    for pattern in DOC_GLOBS:
        for p in sorted(root.glob(pattern)):
            if p.is_file() and p not in seen:
                seen.add(p)
                files.append(p)
    total_links = 0
    issues: list[LinkIssue] = []
    for f in files:
        n, file_issues = lint_file(f, root)
        total_links += n
        issues.extend(file_issues)
    return len(files), total_links, issues


def build_report(n_files: int, n_links: int, issues: list[LinkIssue]) -> SreReport:
    n_missing_file = sum(1 for i in issues if i.kind == "missing_file")
    n_missing_anchor = sum(1 for i in issues if i.kind == "missing_anchor")
    severity: Severity = worst(
        "red" if n_missing_file else "green",
        "yellow" if n_missing_anchor else "green",
    )
    summary = (
        f"{n_files} fichier(s) · {n_links} lien(s) · "
        f"{n_missing_file} fichier(s) manquant(s) · {n_missing_anchor} ancre(s) manquante(s)"
    )
    detail = "\n".join(f"- {i.source_file}:{i.line} → {i.target} ({i.detail})" for i in issues[:20])
    return SreReport(severity, summary, detail)


class DocLinterScript(BaseSreScript):
    """Détecte les liens internes morts dans la documentation."""

    name = "doc_linter"

    def __init__(self, *, poles_root: Path = POLES_DIR, root: Path | None = None) -> None:
        super().__init__(poles_root=poles_root)
        self._root = root or REPO_ROOT

    async def check(self) -> SreReport:
        n_files, n_links, issues = scan_docs(self._root)
        return build_report(n_files, n_links, issues)


__all__ = [
    "DOC_GLOBS",
    "DocLinterScript",
    "LinkIssue",
    "build_report",
    "lint_file",
    "scan_docs",
    "slugify_heading",
]
