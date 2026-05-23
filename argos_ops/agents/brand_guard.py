"""BrandGuardBot — cohérence ton / tagline / signature sur drafts sortants.

Scanne les drafts produits par les autres bots Marketing/Comm (content,
newsletter, press release, case study, crisis, outbound) et signale les
violations des règles brand canoniques via :mod:`argos_ops.comm.brand`.

Pipeline shadow strict :

1. Scan récursif des extensions `.md` sous les dossiers cibles
2. Pour chaque draft, applique :func:`argos_ops.comm.brand.audit_text`
3. Aggrege les issues par sévérité et par fichier
4. Écrit un rapport ``data/comm/brand_audits/<date>.md``
5. Notifie Discord (jaune si warnings, rouge si errors)

Ne modifie aucun draft — c'est au founder de corriger.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from loguru import logger

from argos_ops.agents.base import BaseAgent, RunResult
from argos_ops.comm.brand import BrandIssue, audit_text
from argos_ops.config import REPO_ROOT, get_settings
from argos_ops.notifications.discord import (
    GREEN,
    RED,
    YELLOW,
    Embed,
    EmbedField,
    send_embed,
)

# Dossiers scannés (ajouter au fil des sprints)
SCAN_TARGETS: tuple[Path, ...] = (
    REPO_ROOT / "data" / "content" / "drafts",
    REPO_ROOT / "data" / "newsletters" / "drafts",
    REPO_ROOT / "data" / "comm" / "press_releases",
    REPO_ROOT / "data" / "marketing" / "case_studies",
    REPO_ROOT / "data" / "marketing" / "testimonial_drafts",
    REPO_ROOT / "data" / "seo" / "backlink_drafts",
)
AUDITS_DIR = REPO_ROOT / "data" / "comm" / "brand_audits"


@dataclass
class FileAudit:
    path: Path
    issues: list[BrandIssue] = field(default_factory=list)

    @property
    def error_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "error")

    @property
    def warning_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "warning")


@dataclass
class BrandReport:
    audits: list[FileAudit] = field(default_factory=list)
    digest_path: Path | None = None

    @property
    def total_files(self) -> int:
        return len(self.audits)

    @property
    def files_with_issues(self) -> int:
        return sum(1 for a in self.audits if a.issues)

    @property
    def total_errors(self) -> int:
        return sum(a.error_count for a in self.audits)

    @property
    def total_warnings(self) -> int:
        return sum(a.warning_count for a in self.audits)

    @property
    def color(self) -> int:
        if self.total_errors > 0:
            return RED
        if self.total_warnings > 0:
            return YELLOW
        return GREEN

    def summary(self) -> str:
        return (
            f"files={self.total_files} with_issues={self.files_with_issues} "
            f"errors={self.total_errors} warnings={self.total_warnings}"
        )


def scan_targets(targets: tuple[Path, ...] | None = None) -> list[Path]:
    targets = targets or SCAN_TARGETS
    out: list[Path] = []
    for root in targets:
        if not root.exists():
            continue
        out.extend(sorted(root.rglob("*.md")))
    return out


def audit_drafts(paths: list[Path]) -> list[FileAudit]:
    audits: list[FileAudit] = []
    for path in paths:
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            logger.warning(f"BrandGuardBot — lecture {path.name} : {exc}")
            continue
        audits.append(FileAudit(path=path, issues=audit_text(text)))
    return audits


def write_audit_digest(report: BrandReport, *, now: datetime | None = None) -> Path:
    now = now or datetime.now(UTC)
    AUDITS_DIR.mkdir(parents=True, exist_ok=True)
    path = AUDITS_DIR / f"{now.date().isoformat()}.md"
    lines = [
        f"# Brand audit — {now.date()}",
        "",
        f"- Fichiers scannés : {report.total_files}",
        f"- Avec issues : {report.files_with_issues}",
        f"- Erreurs : {report.total_errors}",
        f"- Warnings : {report.total_warnings}",
        "",
    ]
    counts_by_rule: Counter[str] = Counter()
    for audit in report.audits:
        if not audit.issues:
            continue
        rel = audit.path.relative_to(REPO_ROOT)
        lines.append(f"## {rel}")
        for issue in audit.issues:
            lines.append(f"- **[{issue.severity}]** ({issue.rule_id}) {issue.message}")
            counts_by_rule[issue.rule_id] += 1
        lines.append("")
    if counts_by_rule:
        lines.extend(["## Top rules violées", ""])
        for rule, n in counts_by_rule.most_common():
            lines.append(f"- {rule} : {n}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def build_brand_embed(report: BrandReport) -> Embed:
    fields = [
        EmbedField(name="Fichiers scannés", value=str(report.total_files), inline=True),
        EmbedField(name="Avec issues", value=str(report.files_with_issues), inline=True),
        EmbedField(name="Erreurs", value=str(report.total_errors), inline=True),
        EmbedField(name="Warnings", value=str(report.total_warnings), inline=True),
    ]
    return Embed(
        title="Argos — BrandGuardBot",
        color=report.color,
        fields=fields,
        footer="Argos Ops • BrandGuardBot",
    )


class BrandGuardBot(BaseAgent):
    """Audit brand consistency sur les drafts sortants."""

    name = "BrandGuardBot"
    command = "/run-brand-audit"
    breaker_name = "BrandGuardBot"

    async def run(self) -> RunResult:
        paths = scan_targets()
        audits = audit_drafts(paths)
        report = BrandReport(audits=audits)

        if audits:
            report.digest_path = write_audit_digest(report)

        settings = get_settings()
        webhook = settings.discord_webhook_alerts or settings.discord_webhook_ops_logs
        if webhook is not None and (report.total_errors or report.total_warnings):
            try:
                await send_embed(webhook, build_brand_embed(report))
            except Exception as exc:
                logger.warning(f"BrandGuardBot — notif Discord : {exc}")

        return RunResult(status="success", output_summary=report.summary())


__all__ = [
    "AUDITS_DIR",
    "SCAN_TARGETS",
    "BrandGuardBot",
    "BrandReport",
    "FileAudit",
    "audit_drafts",
    "build_brand_embed",
    "scan_targets",
    "write_audit_digest",
]
