"""DependencyAuditor — AppSec de la flotte (P22.C Tech/SRE Sprint 4).

Inventorie les dépendances Python du projet via ``uv export`` puis
interroge `OSV.dev <https://osv.dev>`_ (API publique gratuite) pour
détecter les CVE. Alerte Discord si ≥1 vuln critique/high.

Politique anti-spam :
- **Silence** Discord si aucune vuln critique/high
- **Embed jaune** si ≥1 vuln severity ``MEDIUM``
- **Embed rouge** si ≥1 vuln severity ``HIGH`` ou ``CRITICAL``

Choix techniques :
- ``uv export --format requirements-txt --no-hashes`` (rapide, déterministe,
  pas de dépendance lourde sur ``uv tree``)
- OSV.dev batch query : 1 seul POST pour tout l'inventaire, pas de
  N+1 par paquet
- Severities mappées vers les niveaux CVSS classiques (NONE/LOW/MEDIUM/HIGH/CRITICAL)

Cf. plan ``docs/ARGOS_OPS_PLAN.md`` Annexe D § 7 Tech/SRE, Sprint 4.
"""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal

import httpx
from loguru import logger

from argos_ops.agents._watcher_base import color_title, emit_alert_or_silence
from argos_ops.agents.base import BaseAgent, RunResult
from argos_ops.notifications.discord import GREEN, RED, YELLOW, Embed, EmbedField

Severity = Literal["UNKNOWN", "LOW", "MEDIUM", "HIGH", "CRITICAL"]

OSV_QUERYBATCH_URL = "https://api.osv.dev/v1/querybatch"
OSV_VULN_URL_TEMPLATE = "https://api.osv.dev/v1/vulns/{vuln_id}"
HTTP_TIMEOUT = 20.0

SEVERITY_ALERT: frozenset[Severity] = frozenset({"HIGH", "CRITICAL"})
SEVERITY_WARN: frozenset[Severity] = frozenset({"MEDIUM"})

# ``package==version`` extrait depuis ``uv export`` (ignore comments/extras)
_REQ_LINE_RE = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]*)\s*==\s*([0-9][^\s;]*)")


@dataclass(frozen=True)
class Dependency:
    """Une dépendance ``name==version`` inventoriée."""

    name: str
    version: str


@dataclass(frozen=True)
class Vulnerability:
    """Une CVE trouvée sur OSV.dev."""

    dep: Dependency
    vuln_id: str
    severity: Severity
    summary: str


@dataclass(frozen=True)
class DependencyAuditReport:
    """Résultat agrégé du run DependencyAuditor."""

    vulnerabilities: list[Vulnerability]
    total_deps_scanned: int
    should_alert: bool
    alert_color: int
    summary: str


# =============================================================================
# Inventaire
# =============================================================================
def parse_requirements(content: str) -> list[Dependency]:
    """Extrait la liste ``name==version`` depuis un export pip ``requirements.txt``."""
    deps: list[Dependency] = []
    seen: set[str] = set()
    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or line.startswith("-"):
            continue
        match = _REQ_LINE_RE.match(line)
        if not match:
            continue
        name = match.group(1).lower()
        version = match.group(2)
        key = f"{name}=={version}"
        if key in seen:
            continue
        seen.add(key)
        deps.append(Dependency(name=name, version=version))
    return deps


async def export_requirements(cwd: str | None = None) -> str:
    """Lance ``uv export`` et retourne le contenu pip-style.

    Erreur subprocess → :class:`RuntimeError` explicite.
    """
    process = await asyncio.create_subprocess_exec(
        "uv",
        "export",
        "--format",
        "requirements-txt",
        "--no-hashes",
        "--no-emit-project",
        cwd=cwd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()
    if process.returncode != 0:
        raise RuntimeError(
            f"`uv export` failed (rc={process.returncode}) : {stderr.decode(errors='replace')[:200]}"
        )
    return stdout.decode(errors="replace")


# =============================================================================
# Query OSV.dev
# =============================================================================
def _map_severity(raw: list[dict[str, Any]] | None) -> Severity:
    """Convertit la liste ``severity`` OSV en niveau CVSS canonique.

    OSV expose ``score`` soit en numérique (``9.8``), soit en CVSS
    vector (``"CVSS:3.1/AV:N/.../A:H/9.8"``). Le score réel est
    toujours **le dernier** nombre du vector — on prend donc le
    dernier match, pas le premier (sinon on récupèrerait la version
    CVSS « 3.1 » et on sous-évaluerait massivement).
    """
    if not raw:
        return "UNKNOWN"
    score: float | None = None
    for entry in raw:
        value = entry.get("score")
        if isinstance(value, int | float):
            score = max(score or 0.0, float(value))
            continue
        if isinstance(value, str):
            matches = re.findall(r"\d+(?:\.\d+)?", value)
            if matches:
                score = max(score or 0.0, float(matches[-1]))
    if score is None:
        return "UNKNOWN"
    if score >= 9.0:
        return "CRITICAL"
    if score >= 7.0:
        return "HIGH"
    if score >= 4.0:
        return "MEDIUM"
    if score > 0.0:
        return "LOW"
    return "UNKNOWN"


async def _fetch_vuln_details(
    client: httpx.AsyncClient, vuln_id: str
) -> tuple[Severity, str]:
    """GET ``/v1/vulns/{id}`` pour récupérer severity + summary."""
    response = await client.get(OSV_VULN_URL_TEMPLATE.format(vuln_id=vuln_id))
    response.raise_for_status()
    body = response.json()
    severity = _map_severity(body.get("severity"))
    summary = body.get("summary") or body.get("details") or vuln_id
    return severity, summary[:200]


async def query_osv(deps: list[Dependency]) -> list[Vulnerability]:
    """Interroge OSV.dev en batch puis fetch les détails de chaque vuln.

    OSV ``querybatch`` ne renvoie que les IDs ; il faut un GET par
    vuln pour avoir la severity. On parallèle ces GET via gather.
    """
    if not deps:
        return []

    queries = [
        {"package": {"name": d.name, "ecosystem": "PyPI"}, "version": d.version}
        for d in deps
    ]
    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
        response = await client.post(OSV_QUERYBATCH_URL, json={"queries": queries})
        response.raise_for_status()
        results = response.json().get("results", [])

        detail_jobs: list[tuple[Dependency, str]] = []
        for dep, result in zip(deps, results, strict=False):
            for vuln in result.get("vulns") or []:
                vuln_id = vuln.get("id")
                if not vuln_id:
                    continue
                detail_jobs.append((dep, vuln_id))

        if not detail_jobs:
            return []

        async def _enrich(dep: Dependency, vuln_id: str) -> Vulnerability:
            try:
                severity, summary = await _fetch_vuln_details(client, vuln_id)
            except Exception as exc:
                logger.warning(f"OSV detail fetch failed for {vuln_id}: {exc}")
                severity = "UNKNOWN"
                summary = vuln_id
            return Vulnerability(
                dep=dep, vuln_id=vuln_id, severity=severity, summary=summary
            )

        return await asyncio.gather(*(_enrich(dep, vid) for dep, vid in detail_jobs))


# =============================================================================
# Décision d'alerte
# =============================================================================
def build_report(
    vulnerabilities: list[Vulnerability], total_deps_scanned: int
) -> DependencyAuditReport:
    """``HIGH``/``CRITICAL`` → rouge, ``MEDIUM`` → jaune, sinon silence."""
    has_alert = any(v.severity in SEVERITY_ALERT for v in vulnerabilities)
    has_warn = any(v.severity in SEVERITY_WARN for v in vulnerabilities)
    should_alert = has_alert or has_warn

    if has_alert:
        alert_color = RED
    elif has_warn:
        alert_color = YELLOW
    else:
        alert_color = GREEN

    crit = sum(1 for v in vulnerabilities if v.severity == "CRITICAL")
    high = sum(1 for v in vulnerabilities if v.severity == "HIGH")
    med = sum(1 for v in vulnerabilities if v.severity == "MEDIUM")
    low = sum(1 for v in vulnerabilities if v.severity == "LOW")
    unknown = sum(1 for v in vulnerabilities if v.severity == "UNKNOWN")
    summary = (
        f"{crit} CRITICAL · {high} HIGH · {med} MEDIUM · {low} LOW · {unknown} UNKNOWN"
        f" (sur {total_deps_scanned} deps)"
    )

    return DependencyAuditReport(
        vulnerabilities=vulnerabilities,
        total_deps_scanned=total_deps_scanned,
        should_alert=should_alert,
        alert_color=alert_color,
        summary=summary,
    )


# =============================================================================
# Formatting
# =============================================================================
_SEVERITY_ICON: dict[Severity, str] = {
    "CRITICAL": "[CRIT]",
    "HIGH": "[HIGH]",
    "MEDIUM": "[MED]",
    "LOW": "[LOW]",
    "UNKNOWN": "[UNK]",
}


def _format_vuln_value(vuln: Vulnerability) -> str:
    return (
        f"`{vuln.dep.name}=={vuln.dep.version}` · {vuln.vuln_id}\n"
        f"{vuln.summary}"
    )


def build_dependency_embed(
    report: DependencyAuditReport, *, now: datetime | None = None
) -> Embed:
    """Construit l'embed Discord — un field par vuln MEDIUM+ (LOW masqué)."""
    now = now or datetime.now(UTC)
    fields = [
        EmbedField(
            name=f"{_SEVERITY_ICON[v.severity]} {v.dep.name}",
            value=_format_vuln_value(v)[:1020],
            inline=False,
        )
        for v in report.vulnerabilities
        if v.severity in SEVERITY_ALERT or v.severity in SEVERITY_WARN
    ]
    title_status = color_title(report.alert_color, green=GREEN, yellow=YELLOW, red=RED)
    return Embed(
        title=f"DependencyAuditor — {title_status}",
        description=report.summary,
        color=report.alert_color,
        fields=fields,
        footer="Argos Ops • DependencyAuditor",
        timestamp=now.isoformat(),
    )


# =============================================================================
# Agent
# =============================================================================
class DependencyAuditor(BaseAgent):
    """AppSec — scan dépendances + check CVE via OSV.dev."""

    name = "DependencyAuditor"
    command = "/run-dep-audit"
    breaker_name = None

    async def run(self) -> RunResult:
        raw = await export_requirements()
        deps = parse_requirements(raw)
        vulnerabilities = await query_osv(deps)
        report = build_report(vulnerabilities, total_deps_scanned=len(deps))
        return await emit_alert_or_silence(
            report, embed_builder=build_dependency_embed, agent_name=self.name
        )


__all__ = [
    "HTTP_TIMEOUT",
    "OSV_QUERYBATCH_URL",
    "OSV_VULN_URL_TEMPLATE",
    "SEVERITY_ALERT",
    "SEVERITY_WARN",
    "Dependency",
    "DependencyAuditReport",
    "DependencyAuditor",
    "Severity",
    "Vulnerability",
    "build_dependency_embed",
    "build_report",
    "export_requirements",
    "parse_requirements",
    "query_osv",
]
