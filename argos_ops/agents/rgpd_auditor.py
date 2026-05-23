"""RGPDAuditor — DPO de la flotte (P22.E Compliance Sprint 8).

Scanne le code source à la recherche de motifs de collecte PII (email,
téléphone, IP, nom, adresse, pièce d'identité) et croise les findings
avec le registre RGPD ``data/compliance/rgpd_registry.yaml``.

Politique anti-spam :
- **Silence** Discord si tout finding PII est couvert par une entrée
  du registre (par chemin ou par préfixe de chemin)
- **Embed jaune** si ≥1 finding non couvert (collecte non documentée)
- **Embed rouge** si le registre est introuvable (faute professionnelle
  RGPD — il DOIT exister)

Cf. plan ``docs/ARGOS_OPS_PLAN.md`` Annexe D § 9 Compliance, Sprint 8.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import yaml

from argos_ops.agents._watcher_base import color_title, emit_alert_or_silence
from argos_ops.agents.base import BaseAgent, RunResult
from argos_ops.compliance import PIIFinding, scan_pii_collectors
from argos_ops.config import REPO_ROOT
from argos_ops.notifications.discord import GREEN, RED, YELLOW, Embed, EmbedField

DEFAULT_REGISTRY_PATH: Path = REPO_ROOT / "data" / "compliance" / "rgpd_registry.yaml"
DEFAULT_SCAN_ROOT: Path = REPO_ROOT / "argos_ops"


@dataclass(frozen=True)
class CoverageFinding:
    """Un finding PII enrichi avec son statut de couverture registre."""

    finding: PIIFinding
    covered: bool
    covering_entry: str | None


@dataclass(frozen=True)
class RGPDAuditReport:
    """Résultat agrégé du run RGPDAuditor."""

    findings: list[CoverageFinding]
    total_scanned: int
    registry_present: bool
    should_alert: bool
    alert_color: int
    summary: str


# =============================================================================
# Lecture registre
# =============================================================================
def load_registry_paths(path: Path) -> list[str]:
    """Lit le registre RGPD et retourne la liste des préfixes de fichiers couverts.

    Format attendu (YAML) ::

        traitements:
          - nom: "Lead BtoB outbound"
            base_legale: "intérêt légitime"
            paths:
              - argos_ops/agents/outbound_bot.py
              - argos_ops/sales/

    Les préfixes sont normalisés (slash forward + sans trailing).
    """
    if not path.exists():
        return []
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    prefixes: list[str] = []
    for entry in raw.get("traitements", []) or []:
        for p in entry.get("paths", []) or []:
            if isinstance(p, str) and p:
                prefixes.append(p.replace("\\", "/").rstrip("/"))
    return prefixes


# =============================================================================
# Scan
# =============================================================================
def scan_repo(root: Path) -> list[PIIFinding]:
    """Scan récursif des ``.py`` sous ``root``."""
    if not root.exists():
        return []
    findings: list[PIIFinding] = []
    for py in root.rglob("*.py"):
        # Skip caches Python et fichiers de test
        if "__pycache__" in py.parts:
            continue
        findings.extend(scan_pii_collectors(py))
    return findings


def cross_reference(
    findings: list[PIIFinding], registry_prefixes: list[str], *, repo_root: Path
) -> list[CoverageFinding]:
    """Marque chaque finding comme couvert / non couvert par le registre.

    Match par préfixe de chemin relatif à ``repo_root``. Si aucun
    préfixe ne matche, la collecte est considérée non documentée.
    """
    normalized_prefixes = [p.replace("\\", "/") for p in registry_prefixes]
    out: list[CoverageFinding] = []
    for finding in findings:
        try:
            rel = finding.path.relative_to(repo_root).as_posix()
        except ValueError:
            rel = finding.path.as_posix()
        match = next(
            (p for p in normalized_prefixes if rel == p or rel.startswith(p + "/")),
            None,
        )
        out.append(
            CoverageFinding(
                finding=finding, covered=match is not None, covering_entry=match
            )
        )
    return out


# =============================================================================
# Décision
# =============================================================================
def build_report(
    coverage: list[CoverageFinding],
    *,
    total_scanned: int,
    registry_present: bool,
) -> RGPDAuditReport:
    """Construit le report avec couleur d'alerte."""
    uncovered = [c for c in coverage if not c.covered]
    if not registry_present:
        alert_color = RED
        should_alert = True
        summary = "registre RGPD introuvable (FAUTE PROFESSIONNELLE)"
    elif uncovered:
        alert_color = YELLOW
        should_alert = True
        summary = (
            f"{len(uncovered)} finding(s) PII non documenté(s) "
            f"sur {len(coverage)} (scan {total_scanned} fichiers)"
        )
    else:
        alert_color = GREEN
        should_alert = False
        summary = (
            f"tous les {len(coverage)} finding(s) PII sont au registre "
            f"(scan {total_scanned} fichiers)"
        )
    return RGPDAuditReport(
        findings=coverage,
        total_scanned=total_scanned,
        registry_present=registry_present,
        should_alert=should_alert,
        alert_color=alert_color,
        summary=summary,
    )


# =============================================================================
# Formatting
# =============================================================================
def _format_finding(cov: CoverageFinding, *, repo_root: Path) -> str:
    try:
        rel = cov.finding.path.relative_to(repo_root).as_posix()
    except ValueError:
        rel = cov.finding.path.as_posix()
    return (
        f"`{rel}:{cov.finding.line_no}` · {cov.finding.category}\n"
        f"{cov.finding.snippet}"
    )[:1020]


def build_rgpd_embed(
    report: RGPDAuditReport,
    *,
    repo_root: Path = REPO_ROOT,
    now: datetime | None = None,
) -> Embed:
    """Embed Discord — un field par finding non couvert (max 10)."""
    now = now or datetime.now(UTC)
    uncovered = [c for c in report.findings if not c.covered][:10]
    fields = [
        EmbedField(
            name=f"[GAP] {c.finding.category}",
            value=_format_finding(c, repo_root=repo_root),
            inline=False,
        )
        for c in uncovered
    ]
    title_status = color_title(report.alert_color, green=GREEN, yellow=YELLOW, red=RED)
    return Embed(
        title=f"RGPDAuditor — {title_status}",
        description=report.summary,
        color=report.alert_color,
        fields=fields,
        footer="Argos Ops • RGPDAuditor",
        timestamp=now.isoformat(),
    )


# =============================================================================
# Agent
# =============================================================================
class RGPDAuditor(BaseAgent):
    """DPO — scanne le code pour collecte PII vs registre RGPD."""

    name = "RGPDAuditor"
    command = "/run-rgpd-audit"
    breaker_name = None
    ai_act_risk_class = "minimal"  # Audit interne, pas de décision sur sujets

    def __init__(
        self,
        *,
        registry_path: Path = DEFAULT_REGISTRY_PATH,
        scan_root: Path = DEFAULT_SCAN_ROOT,
        repo_root: Path = REPO_ROOT,
    ) -> None:
        self._registry_path = registry_path
        self._scan_root = scan_root
        self._repo_root = repo_root

    async def run(self) -> RunResult:
        registry_present = self._registry_path.exists()
        prefixes = load_registry_paths(self._registry_path)
        findings = scan_repo(self._scan_root)
        # Compte total fichiers scannés pour le résumé (info contextuelle)
        total_scanned = sum(
            1
            for _ in self._scan_root.rglob("*.py")
            if "__pycache__" not in _.parts
        )
        coverage = cross_reference(findings, prefixes, repo_root=self._repo_root)
        report = build_report(
            coverage,
            total_scanned=total_scanned,
            registry_present=registry_present,
        )
        return await emit_alert_or_silence(
            report,
            embed_builder=lambda r: build_rgpd_embed(r, repo_root=self._repo_root),
            agent_name=self.name,
        )


__all__ = [
    "DEFAULT_REGISTRY_PATH",
    "DEFAULT_SCAN_ROOT",
    "CoverageFinding",
    "RGPDAuditReport",
    "RGPDAuditor",
    "build_report",
    "build_rgpd_embed",
    "cross_reference",
    "load_registry_paths",
    "scan_repo",
]
