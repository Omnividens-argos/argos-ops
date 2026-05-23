"""DocLinter — Technical Writer (Sprint 13).

Scanne ``docs/**/*.md`` (et ``README.md`` racine) à la recherche de liens
internes morts (chemin relatif qui ne pointe sur aucun fichier réel) et
d'anchors qui ne matchent aucun heading.

Pas de fetch HTTP des liens externes (D-017 — pas de réseau pour un check
quotidien doc). Si plus tard on veut auditer les liens externes, on
ajoutera une option ``--check-external`` séparée.

Politique alerte :
- **silence (vert)** si 0 lien mort
- **embed jaune** si ≥1 anchor mort (heading renommé probablement)
- **embed rouge** si ≥1 chemin fichier mort (référence cassée)
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from loguru import logger

from argos_ops.agents._watcher_base import color_title, emit_alert_or_silence
from argos_ops.agents.base import BaseAgent, RunResult
from argos_ops.config import REPO_ROOT
from argos_ops.notifications.discord import GREEN, RED, YELLOW, Embed, EmbedField

DEFAULT_ROOT: Path = REPO_ROOT
DOCS_GLOBS: tuple[str, ...] = ("docs/**/*.md", "README.md", "CLAUDE.md")

# Capture les liens markdown [text](target) — pas les images ![alt](src)
_LINK_RE = re.compile(r"(?<!!)\[([^\]]+)\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$", re.MULTILINE)

LinkIssueKind = Literal["missing_file", "missing_anchor"]


@dataclass(frozen=True)
class LinkIssue:
    """Lien interne cassé détecté dans un fichier doc."""

    source_file: Path
    line_number: int
    link_text: str
    target: str
    kind: LinkIssueKind
    detail: str


@dataclass(frozen=True)
class DocLintReport:
    """Bilan d'un run DocLinter."""

    files_scanned: int
    links_checked: int
    issues: list[LinkIssue]
    should_alert: bool
    alert_color: int
    summary: str


def _slugify_heading(text: str) -> str:
    """Slugify GitHub-style — minuscule, espaces → tirets, ponctuation virée."""
    cleaned = re.sub(r"[^\w\s-]", "", text.lower(), flags=re.UNICODE)
    cleaned = re.sub(r"\s+", "-", cleaned.strip())
    return cleaned


def _extract_anchors(text: str) -> set[str]:
    """Liste des anchors GitHub-style pour un fichier markdown."""
    return {_slugify_heading(m.group(2)) for m in _HEADING_RE.finditer(text)}


def _is_external(target: str) -> bool:
    return (
        target.startswith("http://")
        or target.startswith("https://")
        or target.startswith("mailto:")
        or target.startswith("tel:")
    )


def discover_docs(root: Path) -> list[Path]:
    """Liste les markdown à auditer, dans un ordre déterministe."""
    found: set[Path] = set()
    for pattern in DOCS_GLOBS:
        for p in root.glob(pattern):
            if p.is_file():
                found.add(p.resolve())
    return sorted(found)


def lint_file(path: Path, *, root: Path) -> tuple[int, list[LinkIssue]]:
    """Audit un fichier markdown. Retourne (nb_links_checked, issues).

    ``root`` est la racine du repo pour résoudre les chemins relatifs.
    """
    text = path.read_text(encoding="utf-8")
    issues: list[LinkIssue] = []
    links_checked = 0

    line_starts = [0]
    for idx, ch in enumerate(text):
        if ch == "\n":
            line_starts.append(idx + 1)

    def _line_for(pos: int) -> int:
        # binary-search-lite
        lo, hi = 0, len(line_starts) - 1
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if line_starts[mid] <= pos:
                lo = mid
            else:
                hi = mid - 1
        return lo + 1

    for match in _LINK_RE.finditer(text):
        link_text, target = match.group(1), match.group(2)
        if _is_external(target):
            continue
        links_checked += 1
        line = _line_for(match.start())

        # split anchor / file
        anchor: str | None
        if "#" in target:
            file_part, anchor = target.split("#", 1)
        else:
            file_part, anchor = target, None

        target_path = path if file_part == "" else (path.parent / file_part).resolve()

        if not target_path.exists():
            issues.append(
                LinkIssue(
                    source_file=path,
                    line_number=line,
                    link_text=link_text,
                    target=target,
                    kind="missing_file",
                    detail=(
                        f"chemin introuvable : "
                        f"{target_path.relative_to(root) if target_path.is_relative_to(root) else target_path}"
                    ),
                )
            )
            continue

        if anchor and target_path.suffix.lower() == ".md":
            try:
                target_text = target_path.read_text(encoding="utf-8")
            except OSError:
                continue
            anchors = _extract_anchors(target_text)
            if _slugify_heading(anchor) not in anchors:
                issues.append(
                    LinkIssue(
                        source_file=path,
                        line_number=line,
                        link_text=link_text,
                        target=target,
                        kind="missing_anchor",
                        detail=f"anchor introuvable : #{anchor}",
                    )
                )
    return links_checked, issues


def build_report(
    *, files_scanned: int, links_checked: int, issues: list[LinkIssue]
) -> DocLintReport:
    """Couleur RED si missing_file, YELLOW si juste missing_anchor."""
    if not issues:
        return DocLintReport(
            files_scanned=files_scanned,
            links_checked=links_checked,
            issues=[],
            should_alert=False,
            alert_color=GREEN,
            summary=f"{files_scanned} fichiers · {links_checked} liens · 0 cassé",
        )

    has_missing_file = any(i.kind == "missing_file" for i in issues)
    color = RED if has_missing_file else YELLOW
    by_kind: dict[str, int] = {}
    for i in issues:
        by_kind[i.kind] = by_kind.get(i.kind, 0) + 1
    summary_parts = [f"{c} {k}" for k, c in by_kind.items()]
    summary = (
        f"{files_scanned} fichiers · {links_checked} liens · "
        f"{' · '.join(summary_parts)}"
    )
    return DocLintReport(
        files_scanned=files_scanned,
        links_checked=links_checked,
        issues=issues,
        should_alert=True,
        alert_color=color,
        summary=summary,
    )


_KIND_ICON: dict[LinkIssueKind, str] = {
    "missing_file": "[404]",
    "missing_anchor": "[ANC]",
}


def build_lint_embed(
    report: DocLintReport, *, now: datetime | None = None, root: Path = DEFAULT_ROOT
) -> Embed:
    """Embed Discord — un field par issue (capped à 10)."""
    now = now or datetime.now(UTC)
    fields = [
        EmbedField(
            name=f"{_KIND_ICON[i.kind]} {i.source_file.relative_to(root)}:{i.line_number}",
            value=f"[{i.link_text}]({i.target}) — {i.detail}"[:1020],
            inline=False,
        )
        for i in report.issues[:10]
    ]
    if len(report.issues) > 10:
        fields.append(
            EmbedField(
                name="…",
                value=f"+{len(report.issues) - 10} issues supplémentaires",
                inline=False,
            )
        )
    title_status = color_title(report.alert_color, green=GREEN, yellow=YELLOW, red=RED)
    return Embed(
        title=f"DocLinter — {title_status}",
        description=report.summary,
        color=report.alert_color,
        fields=fields,
        footer="Argos Ops • DocLinter",
        timestamp=now.isoformat(),
    )


class DocLinter(BaseAgent):
    """Technical Writer — détecte les liens internes morts dans docs/."""

    name = "DocLinter"
    command = "/run-doc-lint"
    breaker_name = None

    def __init__(self, *, root: Path = DEFAULT_ROOT) -> None:
        self._root = root

    async def run(self) -> RunResult:
        docs = discover_docs(self._root)
        if not docs:
            logger.info(f"DocLinter — aucun markdown trouvé sous {self._root}")
            return RunResult(
                status="success",
                output_summary="silence (aucun doc)",
                extras={"alerted": False},
            )

        all_issues: list[LinkIssue] = []
        total_links = 0
        for path in docs:
            checked, issues = lint_file(path, root=self._root)
            total_links += checked
            all_issues.extend(issues)

        report = build_report(
            files_scanned=len(docs), links_checked=total_links, issues=all_issues
        )
        return await emit_alert_or_silence(
            report,
            embed_builder=lambda r: build_lint_embed(r, root=self._root),
            agent_name=self.name,
        )


__all__ = [
    "DEFAULT_ROOT",
    "DOCS_GLOBS",
    "DocLintReport",
    "DocLinter",
    "LinkIssue",
    "LinkIssueKind",
    "build_lint_embed",
    "build_report",
    "discover_docs",
    "lint_file",
]
