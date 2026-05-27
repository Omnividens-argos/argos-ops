"""CVEMonitor — Threat Intel (P22.D Veille Sprint 6).

Distinct du ``DependencyAuditor`` (P22.C) qui scanne notre stack à nous :
celui-ci surveille la stack **déclarée par les prospects** dans
``data/crm/customers.yaml`` (``stack:`` array : ``nginx``, ``wordpress``,
``log4j``, etc.) et alerte si une CVE high/critical sort sur ces
packages.

Politique anti-spam :
- **Silence** Discord si aucune CVE nouvelle HIGH/CRITICAL sur la stack
- **Embed jaune** si ≥1 CVE MEDIUM
- **Embed rouge** si ≥1 CVE HIGH/CRITICAL

L'état "déjà vu" est tracé via les IDs OSV (``data/cve/seen_vulns.json``)
pour ne pas réalerter sur la même CVE chaque jour.

Cf. plan ``docs/ARGOS_OPS_PLAN.md`` Annexe D § 8 Veille, Sprint 6+.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import yaml
from loguru import logger

from argos_ops.agents._fetcher_base import fetch
from argos_ops.agents._watcher_base import color_title, emit_alert_or_silence
from argos_ops.agents.base import BaseAgent, RunResult
from argos_ops.agents.dependency_auditor import (
    OSV_QUERYBATCH_URL,
    OSV_VULN_URL_TEMPLATE,
    Severity,
    _map_severity,
)
from argos_ops.config import REPO_ROOT
from argos_ops.notifications.discord import GREEN, RED, YELLOW, Embed, EmbedField

SERVICE_NAME = "cve-monitor"
DEFAULT_CUSTOMERS_PATH: Path = REPO_ROOT / "data" / "crm" / "customers.yaml"
DEFAULT_SEEN_PATH: Path = REPO_ROOT / "data" / "cve" / "seen_vulns.json"

SEVERITY_ALERT: frozenset[Severity] = frozenset({"HIGH", "CRITICAL"})
SEVERITY_WARN: frozenset[Severity] = frozenset({"MEDIUM"})


@dataclass(frozen=True)
class StackPackage:
    """Un package déclaré dans la stack d'un prospect/client."""

    customer_name: str
    ecosystem: str  # "npm" | "PyPI" | "Maven" | "OSS-Fuzz" | "Linux" | …
    name: str
    version: str | None  # peut être None ("nginx" sans version connue)


@dataclass(frozen=True)
class CVEAlert:
    package: StackPackage
    vuln_id: str
    severity: Severity
    summary: str


@dataclass(frozen=True)
class CVEReport:
    alerts: list[CVEAlert]
    total_packages_scanned: int
    should_alert: bool
    alert_color: int
    summary: str


# =============================================================================
# Config
# =============================================================================
def load_stack_packages(path: Path = DEFAULT_CUSTOMERS_PATH) -> list[StackPackage]:
    """Lit ``customers.yaml`` et extrait la stack de chaque client.

    Schéma attendu (chaque client peut avoir une ``stack:``) ::

        customers:
          - name: "Acme"
            domain: "acme.test"
            stack:
              - { ecosystem: "PyPI",    name: "django",  version: "4.2.1" }
              - { ecosystem: "npm",     name: "lodash",  version: "4.17.0" }
              - { ecosystem: "OSS-Fuzz", name: "nginx",  version: "1.24.0" }
    """
    if not path.exists():
        return []
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    out: list[StackPackage] = []
    for entry in raw.get("customers", []):
        customer_name = entry.get("name") or "<unknown>"
        for pkg in entry.get("stack", []) or []:
            ecosystem = pkg.get("ecosystem")
            name = pkg.get("name")
            if not ecosystem or not name:
                continue
            out.append(
                StackPackage(
                    customer_name=str(customer_name),
                    ecosystem=str(ecosystem),
                    name=str(name),
                    version=str(pkg["version"]) if pkg.get("version") else None,
                )
            )
    return out


# =============================================================================
# Seen vulns
# =============================================================================
def load_seen_vulns(path: Path = DEFAULT_SEEN_PATH) -> set[str]:
    if not path.exists():
        return set()
    try:
        return set(json.loads(path.read_text(encoding="utf-8")).get("seen", []))
    except (json.JSONDecodeError, ValueError) as exc:
        logger.warning(f"CVEMonitor seen_vulns corrompu: {exc}")
        return set()


def save_seen_vulns(seen: set[str], *, path: Path = DEFAULT_SEEN_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"seen": sorted(seen), "saved_at": datetime.now(UTC).isoformat()}),
        encoding="utf-8",
    )


# =============================================================================
# OSV
# =============================================================================
async def query_osv(packages: list[StackPackage]) -> list[CVEAlert]:
    """Batch OSV pour tous les packages (skip ceux sans version)."""
    queried = [p for p in packages if p.version]
    if not queried:
        return []
    payload = {
        "queries": [
            {
                "package": {"name": p.name, "ecosystem": p.ecosystem},
                "version": p.version,
            }
            for p in queried
        ]
    }
    response = await fetch(
        OSV_QUERYBATCH_URL,
        service=SERVICE_NAME,
        method="POST",
        body=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        # On bypass le cache 24h : les CVE peuvent évoluer dans la journée
        bypass_cache=True,
        rate_limit_seconds=0.5,
    )
    try:
        results = json.loads(response.body).get("results", [])
    except json.JSONDecodeError as exc:
        logger.warning(f"CVEMonitor OSV batch payload invalide: {exc}")
        return []

    alerts: list[CVEAlert] = []
    for pkg, result in zip(queried, results, strict=False):
        for vuln in result.get("vulns") or []:
            vuln_id = vuln.get("id")
            if not vuln_id:
                continue
            # Fetch le détail pour avoir la severity (OSV batch ne la renvoie pas)
            try:
                detail_resp = await fetch(
                    OSV_VULN_URL_TEMPLATE.format(vuln_id=vuln_id),
                    service=SERVICE_NAME,
                    bypass_cache=True,
                    rate_limit_seconds=0.5,
                )
                detail = json.loads(detail_resp.body)
            except Exception as exc:
                logger.warning(f"CVEMonitor — détail {vuln_id} échoué: {exc}")
                continue
            severity = _map_severity(detail.get("severity"))
            summary = str(detail.get("summary") or detail.get("details") or vuln_id)[:200]
            alerts.append(
                CVEAlert(package=pkg, vuln_id=vuln_id, severity=severity, summary=summary)
            )
    return alerts


# =============================================================================
# Report
# =============================================================================
def build_report(
    alerts: list[CVEAlert], total_packages: int
) -> CVEReport:
    has_alert = any(a.severity in SEVERITY_ALERT for a in alerts)
    has_warn = any(a.severity in SEVERITY_WARN for a in alerts)
    if has_alert:
        alert_color = RED
    elif has_warn:
        alert_color = YELLOW
    else:
        alert_color = GREEN

    crit = sum(1 for a in alerts if a.severity == "CRITICAL")
    high = sum(1 for a in alerts if a.severity == "HIGH")
    med = sum(1 for a in alerts if a.severity == "MEDIUM")
    summary = (
        f"{crit} CRITICAL · {high} HIGH · {med} MEDIUM "
        f"(stacks scannées : {total_packages})"
    )
    return CVEReport(
        alerts=alerts,
        total_packages_scanned=total_packages,
        should_alert=has_alert or has_warn,
        alert_color=alert_color,
        summary=summary,
    )


_SEVERITY_ICON: dict[Severity, str] = {
    "CRITICAL": "[CRIT]",
    "HIGH": "[HIGH]",
    "MEDIUM": "[MED]",
    "LOW": "[LOW]",
    "UNKNOWN": "[UNK]",
}


def build_cve_embed(report: CVEReport, *, now: datetime | None = None) -> Embed:
    now = now or datetime.now(UTC)
    fields = [
        EmbedField(
            name=f"{_SEVERITY_ICON[alert.severity]} {alert.package.customer_name} · {alert.package.name}",
            value=(
                f"{alert.package.ecosystem} `{alert.package.version}` · {alert.vuln_id}\n"
                f"{alert.summary}"
            )[:1020],
            inline=False,
        )
        for alert in report.alerts
        if alert.severity in SEVERITY_ALERT or alert.severity in SEVERITY_WARN
    ]
    title_status = color_title(report.alert_color, green=GREEN, yellow=YELLOW, red=RED)
    return Embed(
        title=f"CVEMonitor — {title_status}",
        description=report.summary,
        color=report.alert_color,
        fields=fields,
        footer="Argos Ops • CVEMonitor",
        timestamp=now.isoformat(),
    )


class CVEMonitor(BaseAgent):
    """Threat Intel — CVE critiques sur stacks clients déclarées."""

    name = "CVEMonitor"
    command = "/run-cve-monitor"
    breaker_name = None
    ai_act_risk_class = "minimal"

    def __init__(
        self,
        *,
        customers_path: Path = DEFAULT_CUSTOMERS_PATH,
        seen_path: Path = DEFAULT_SEEN_PATH,
    ) -> None:
        self._customers_path = customers_path
        self._seen_path = seen_path

    async def run(self) -> RunResult:
        packages = load_stack_packages(self._customers_path)
        if not packages:
            logger.info(
                f"CVEMonitor — aucune stack déclarée ({self._customers_path})"
            )
            return RunResult(
                status="success",
                output_summary="silence (aucune stack)",
                extras={"alerted": False, "summary": "0 packages"},
            )

        seen = load_seen_vulns(self._seen_path)
        all_alerts = await query_osv(packages)
        new_alerts = [a for a in all_alerts if a.vuln_id not in seen]
        seen.update(a.vuln_id for a in all_alerts)
        save_seen_vulns(seen, path=self._seen_path)

        report = build_report(new_alerts, total_packages=len(packages))
        return await emit_alert_or_silence(
            report, embed_builder=build_cve_embed, agent_name=self.name
        )


__all__ = [
    "DEFAULT_CUSTOMERS_PATH",
    "DEFAULT_SEEN_PATH",
    "SERVICE_NAME",
    "SEVERITY_ALERT",
    "SEVERITY_WARN",
    "CVEAlert",
    "CVEMonitor",
    "CVEReport",
    "StackPackage",
    "build_cve_embed",
    "build_report",
    "load_seen_vulns",
    "load_stack_packages",
    "query_osv",
    "save_seen_vulns",
]
