"""BugTriageBot — QA Lead (P22.G Produit Sprint 11).

Trie les issues GitHub ouvertes (saisies à la main dans
``data/issues/open.yaml`` ou exportées via ``gh issue list --json …
> data/issues/open.yaml``) par sévérité — P0 / P1 / P2 — et propose un
label.

Format YAML attendu ::

    issues:
      - number: 42
        title: "Scan crash sur API GraphQL"
        body: "Stack trace + repro steps..."
        labels: ["bug"]
        opened_at: "2026-05-20"

Le bot écrit ``data/issues/triage_<YYYY-MM-DD>.yaml`` avec sévérité +
label suggéré. Mode shadow strict : pas d'appel ``gh api`` côté Python
(le founder applique les labels à la main). Idempotent.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

import yaml
from loguru import logger

from argos_ops.agents.base import BaseAgent, RunResult
from argos_ops.config import REPO_ROOT, get_settings
from argos_ops.notifications.discord import (
    GREEN,
    ORANGE,
    RED,
    YELLOW,
    Embed,
    EmbedField,
    send_embed,
)

DEFAULT_ISSUES_PATH: Path = REPO_ROOT / "data" / "issues" / "open.yaml"
DEFAULT_TRIAGE_DIR: Path = REPO_ROOT / "data" / "issues"

# Mots-clés sévérité (réutilisés en spirit de cs/scoring.py mais distincts
# pour rester self-contained côté Produit).
_P0_KEYWORDS = (
    "prod down",
    "data loss",
    "perte de données",
    "security",
    "vulnérabilité",
    "rce",
    "csrf",
    "xss",
    "sql injection",
    "crash systemic",
)
_P1_KEYWORDS = (
    "bug",
    "crash",
    "error 500",
    "regression",
    "régression",
    "broken",
    "ne fonctionne plus",
)

# Mapping severity → label suggéré
_SEVERITY_LABEL = {
    "P0": "severity/critical",
    "P1": "severity/major",
    "P2": "severity/minor",
}


@dataclass(frozen=True)
class TriagedIssue:
    """Une issue triée."""

    number: int
    title: str
    severity: str  # P0 | P1 | P2
    suggested_label: str
    reason: str


@dataclass
class BugTriageStats:
    issues_total: int = 0
    p0: int = 0
    p1: int = 0
    p2: int = 0
    triaged: list[TriagedIssue] = field(default_factory=list)

    def summary(self) -> str:
        return (
            f"issues={self.issues_total} p0={self.p0} p1={self.p1} p2={self.p2}"
        )


def _load_issues(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    issues = raw.get("issues", [])
    if not isinstance(issues, list):
        raise ValueError(f"issues/open.yaml malformé : {path}")
    return issues


def classify_severity(title: str, body: str = "", labels: list[str] | None = None) -> str:
    """Classifie une issue P0 / P1 / P2 via mots-clés titre+body+labels."""
    labels = labels or []
    haystack = f"{title}\n{body}\n{' '.join(labels)}".lower()
    for kw in _P0_KEYWORDS:
        if kw in haystack:
            return "P0"
    for kw in _P1_KEYWORDS:
        if kw in haystack:
            return "P1"
    return "P2"


def triage_issues(issues: list[dict[str, Any]]) -> BugTriageStats:
    stats = BugTriageStats(issues_total=len(issues))
    for issue in issues:
        number = int(issue.get("number", 0))
        title = issue.get("title", "")
        body = issue.get("body", "") or ""
        labels = issue.get("labels", []) or []
        severity = classify_severity(title, body, labels)
        suggested_label = _SEVERITY_LABEL[severity]
        triaged = TriagedIssue(
            number=number,
            title=title,
            severity=severity,
            suggested_label=suggested_label,
            reason=f"mots-clés {severity} détectés (titre/body/labels)",
        )
        stats.triaged.append(triaged)
        if severity == "P0":
            stats.p0 += 1
        elif severity == "P1":
            stats.p1 += 1
        else:
            stats.p2 += 1
    # Trie par sévérité descendante (P0 d'abord)
    severity_order = {"P0": 0, "P1": 1, "P2": 2}
    stats.triaged.sort(key=lambda t: severity_order[t.severity])
    return stats


def _persist_triage(path: Path, stats: BugTriageStats, *, day: date) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = {
        "triage_date": day.isoformat(),
        "p0": stats.p0,
        "p1": stats.p1,
        "p2": stats.p2,
        "issues": [
            {
                "number": t.number,
                "title": t.title,
                "severity": t.severity,
                "suggested_label": t.suggested_label,
                "reason": t.reason,
            }
            for t in stats.triaged
        ],
    }
    path.write_text(
        yaml.safe_dump(payload, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )


def build_bug_triage_embed(stats: BugTriageStats) -> Embed:
    if stats.p0 > 0:
        color = RED
    elif stats.p1 > 0:
        color = ORANGE
    elif stats.p2 > 0:
        color = YELLOW
    else:
        color = GREEN
    fields = [
        EmbedField(name="P0", value=str(stats.p0), inline=True),
        EmbedField(name="P1", value=str(stats.p1), inline=True),
        EmbedField(name="P2", value=str(stats.p2), inline=True),
    ]
    high_priority = [t for t in stats.triaged if t.severity in ("P0", "P1")]
    if high_priority:
        lines = [
            f"• [{t.severity}] #{t.number} — {t.title[:60]}"
            for t in high_priority[:5]
        ]
        fields.append(EmbedField(name="Top priorités", value="\n".join(lines), inline=False))
    return Embed(
        title=f"BugTriageBot — {stats.p0} P0 / {stats.p1} P1 / {stats.p2} P2",
        description=(
            "Applique les labels suggérés via `gh issue edit <num> --add-label <label>`."
            if stats.triaged
            else "Aucune issue ouverte."
        ),
        color=color,
        fields=fields,
        footer="Argos Ops • BugTriageBot",
    )


class BugTriageBot(BaseAgent):
    """Classifie les issues GitHub par sévérité + label suggéré."""

    name = "BugTriageBot"
    command = "/run-bug-triage"
    breaker_name = "BugTriageBot"

    def __init__(
        self,
        *,
        issues_path: Path = DEFAULT_ISSUES_PATH,
        triage_dir: Path = DEFAULT_TRIAGE_DIR,
    ) -> None:
        self._issues_path = issues_path
        self._triage_dir = triage_dir

    async def run(self) -> RunResult:
        settings = get_settings()
        issues = _load_issues(self._issues_path)
        if not issues:
            logger.info(f"BugTriageBot — aucune issue ({self._issues_path})")
            return RunResult(status="success", output_summary="silence (no issues)")

        stats = triage_issues(issues)
        today = date.today()
        triage_path = self._triage_dir / f"triage_{today.isoformat()}.yaml"
        _persist_triage(triage_path, stats, day=today)

        webhook = settings.discord_webhook_ops_logs or settings.discord_webhook_alerts
        if webhook is not None and (stats.p0 > 0 or stats.p1 > 0):
            try:
                await send_embed(webhook, build_bug_triage_embed(stats))
            except Exception as exc:
                logger.warning(f"BugTriageBot — notif Discord échouée : {exc}")

        return RunResult(status="success", output_summary=stats.summary())


__all__ = [
    "DEFAULT_ISSUES_PATH",
    "DEFAULT_TRIAGE_DIR",
    "BugTriageBot",
    "BugTriageStats",
    "TriagedIssue",
    "build_bug_triage_embed",
    "classify_severity",
    "triage_issues",
]
