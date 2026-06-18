"""``CVEMonitorScript`` — CVE critiques sur stacks clients (Veille, archi v2).

Porté depuis ``argos_ops.agents.cve_monitor`` (legacy). Bras déterministe :

1. lit ``data/crm/customers.yaml`` (founder-maintained) et extrait la stack
   déclarée par chaque prospect/client (``stack:`` array) ;
2. interroge `OSV.dev <https://osv.dev>`_ en batch (1 POST + 1 GET par vuln),
   sans cache (``bypass_cache=True``) car les CVE évoluent dans la journée ;
3. dédoublonne via l'état "déjà vu" (``data/cve/seen_vulns.json``) pour ne pas
   réalerter sur la même CVE chaque jour ;
4. écrit chaque NOUVELLE CVE MEDIUM+ dans **sa propre mémoire de pôle**
   (``kind="cve"``). LOW/UNKNOWN sont ignorées (anti-bruit).

Pas de Discord, pas de DB, pas de LLM (D-017) : le :class:`VeilleAgent` lit cette
mémoire et agit. La sévérité ne pilote plus une couleur d'embed mais le flag
``important`` (HIGH/CRITICAL) + un tag de sévérité. Idempotent : une CVE
re-détectée a le même corps -> même fait (le socle déduplique par hash) et son
``vuln_id`` est filtré par ``seen`` au run suivant.

Constantes OSV + ``Severity`` + ``_map_severity`` portés ici depuis le legacy
``dependency_auditor`` (pas d'import croisé : cohérence cutover archi v2).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

import yaml
from loguru import logger

from argos_ops.agents._fetcher_base import fetch
from argos_ops.config import REPO_ROOT
from argos_ops.poles.base import BaseScript, ScriptResult
from argos_ops.poles.config import POLES_DIR

SERVICE_NAME = "cve-monitor"
DEFAULT_CUSTOMERS_PATH: Path = REPO_ROOT / "data" / "crm" / "customers.yaml"
DEFAULT_SEEN_PATH: Path = REPO_ROOT / "data" / "cve" / "seen_vulns.json"

# Porté depuis argos_ops.agents.dependency_auditor (legacy) — pas d'import croisé.
Severity = Literal["UNKNOWN", "LOW", "MEDIUM", "HIGH", "CRITICAL"]

OSV_QUERYBATCH_URL = "https://api.osv.dev/v1/querybatch"
OSV_VULN_URL_TEMPLATE = "https://api.osv.dev/v1/vulns/{vuln_id}"

SEVERITY_ALERT: frozenset[Severity] = frozenset({"HIGH", "CRITICAL"})
SEVERITY_WARN: frozenset[Severity] = frozenset({"MEDIUM"})

# Sévérités mémorisées (LOW/UNKNOWN ignorées pour ne pas polluer la mémoire).
_SEVERITY_MEMORIZED: frozenset[Severity] = SEVERITY_ALERT | SEVERITY_WARN


@dataclass(frozen=True)
class StackPackage:
    """Un package déclaré dans la stack d'un prospect/client."""

    customer_name: str
    ecosystem: str  # "npm" | "PyPI" | "Maven" | "OSS-Fuzz" | "Linux" | ...
    name: str
    version: str | None  # peut etre None ("nginx" sans version connue)


@dataclass(frozen=True)
class CVEAlert:
    """Une CVE trouvée sur OSV.dev pour un package d'une stack client."""

    package: StackPackage
    vuln_id: str
    severity: Severity
    summary: str


# =============================================================================
# Mapping de sévérité (porté depuis dependency_auditor._map_severity)
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


# =============================================================================
# Config — stacks clients
# =============================================================================
def load_stack_packages(path: Path = DEFAULT_CUSTOMERS_PATH) -> list[StackPackage]:
    """Lit ``customers.yaml`` et extrait la stack de chaque client.

    Schéma attendu (chaque client peut avoir une ``stack:``) ::

        customers:
          - name: "Acme"
            domain: "acme.test"
            stack:
              - { ecosystem: "PyPI",     name: "django", version: "4.2.1" }
              - { ecosystem: "npm",      name: "lodash", version: "4.17.0" }
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
# État "déjà vu" (anti-réalerte)
# =============================================================================
def load_seen_vulns(path: Path = DEFAULT_SEEN_PATH) -> set[str]:
    """Lit l'ensemble des ``vuln_id`` déjà signalés (vide si absent/corrompu)."""
    if not path.exists():
        return set()
    try:
        return set(json.loads(path.read_text(encoding="utf-8")).get("seen", []))
    except (json.JSONDecodeError, ValueError) as exc:
        logger.warning(f"CVEMonitor seen_vulns corrompu: {exc}")
        return set()


def save_seen_vulns(seen: set[str], *, path: Path = DEFAULT_SEEN_PATH) -> None:
    """Persiste l'ensemble des ``vuln_id`` déjà vus (triés, daté)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"seen": sorted(seen), "saved_at": datetime.now(UTC).isoformat()}),
        encoding="utf-8",
    )


# =============================================================================
# OSV.dev
# =============================================================================
async def query_osv(packages: list[StackPackage]) -> list[CVEAlert]:
    """Batch OSV pour tous les packages (skip ceux sans version).

    OSV ``querybatch`` ne renvoie que les IDs ; un GET par vuln est
    nécessaire pour récupérer la sévérité. Le cache 24h est bypassé car
    les CVE peuvent évoluer dans la journée.
    """
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
# Script
# =============================================================================
class CVEMonitorScript(BaseScript):
    """Surveille les CVE des stacks clients déclarées et les mémorise."""

    pole = "veille"
    name = "cve_monitor"

    def __init__(
        self,
        *,
        poles_root: Path = POLES_DIR,
        customers_path: Path = DEFAULT_CUSTOMERS_PATH,
        seen_path: Path = DEFAULT_SEEN_PATH,
    ) -> None:
        super().__init__(poles_root=poles_root)
        self._customers_path = customers_path
        self._seen_path = seen_path

    async def run(self) -> ScriptResult:
        packages = load_stack_packages(self._customers_path)
        if not packages:
            logger.info(f"CVEMonitor — aucune stack déclarée ({self._customers_path})")
            return ScriptResult(
                status="success",
                summary="silence (aucune stack déclarée)",
                written=[],
            )

        seen = load_seen_vulns(self._seen_path)
        all_alerts = await query_osv(packages)
        new_alerts = [a for a in all_alerts if a.vuln_id not in seen]
        seen.update(a.vuln_id for a in all_alerts)
        save_seen_vulns(seen, path=self._seen_path)

        written = []
        for alert in new_alerts:
            if alert.severity not in _SEVERITY_MEMORIZED:
                continue  # LOW/UNKNOWN ignorées (anti-bruit)
            pkg = alert.package
            version = pkg.version or "version inconnue"
            record = await self.write_memory(
                f"CVE {alert.vuln_id} ({alert.severity}) sur "
                f"{pkg.customer_name}/{pkg.name} {pkg.ecosystem} {version} : "
                f"{alert.summary}",
                kind="cve",
                tags=("cve", alert.severity.lower()),
                important=alert.severity in SEVERITY_ALERT,
                source=OSV_VULN_URL_TEMPLATE.format(vuln_id=alert.vuln_id),
            )
            written.append(record)

        crit = sum(1 for a in new_alerts if a.severity == "CRITICAL")
        high = sum(1 for a in new_alerts if a.severity == "HIGH")
        med = sum(1 for a in new_alerts if a.severity == "MEDIUM")
        summary = f"{crit} CRITICAL / {high} HIGH / {med} MEDIUM"
        return ScriptResult(
            status="success",
            summary=summary,
            written=written,
        )


__all__ = [
    "DEFAULT_CUSTOMERS_PATH",
    "DEFAULT_SEEN_PATH",
    "OSV_QUERYBATCH_URL",
    "OSV_VULN_URL_TEMPLATE",
    "SERVICE_NAME",
    "SEVERITY_ALERT",
    "SEVERITY_WARN",
    "CVEAlert",
    "CVEMonitorScript",
    "Severity",
    "StackPackage",
    "load_seen_vulns",
    "load_stack_packages",
    "query_osv",
    "save_seen_vulns",
]
