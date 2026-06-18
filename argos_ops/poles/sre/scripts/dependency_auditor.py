"""``DependencyAuditorScript`` — CVE sur les dépendances (archi v2, S8).

Exporte les dépendances Python (``uv export``) et interroge l'API publique
**OSV.dev** : rouge si ≥ 1 vulnérabilité HIGH/CRITICAL, jaune si MEDIUM, vert
sinon. Le fournisseur de deps et la requête OSV sont injectables (tests
hermétiques). Si l'outillage est indisponible (``uv`` / réseau), le check
**dégrade en jaune** (« audit impossible ») plutôt que de planter en rouge.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path

import httpx
from loguru import logger

from argos_ops.config import REPO_ROOT
from argos_ops.poles.config import POLES_DIR
from argos_ops.poles.sre.base import BaseSreScript
from argos_ops.poles.sre.report import Severity, SreReport

OSV_BATCH_URL = "https://api.osv.dev/v1/querybatch"
OSV_VULN_URL = "https://api.osv.dev/v1/vulns"
OSV_TIMEOUT = 20.0
SEVERITY_ALERT = frozenset({"CRITICAL", "HIGH"})
SEVERITY_WARN = frozenset({"MEDIUM"})
_SEVERITY_RANK = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1, "UNKNOWN": 0}


@dataclass(frozen=True)
class Dependency:
    name: str
    version: str


@dataclass(frozen=True)
class Vulnerability:
    dep_name: str
    dep_version: str
    vuln_id: str
    severity: str  # CRITICAL | HIGH | MEDIUM | LOW | UNKNOWN
    summary: str


DepsProvider = Callable[[], Awaitable[list[Dependency]]]
OsvQuery = Callable[[list[Dependency]], Awaitable[list[Vulnerability]]]


def parse_requirements(text: str) -> list[Dependency]:
    """Parse une sortie ``requirements.txt`` (name==version), tolérant."""
    deps: list[Dependency] = []
    seen: set[str] = set()
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith(("#", "-")):
            continue
        line = line.split(";")[0].strip()  # retire les markers d'environnement
        if "==" not in line:
            continue
        name, _, version = line.partition("==")
        name = name.split("[")[0].strip().lower()  # retire les extras
        version = version.strip()
        key = f"{name}=={version}"
        if name and version and key not in seen:
            seen.add(key)
            deps.append(Dependency(name, version))
    return deps


def normalize_severity(value: str | None) -> str:
    """Normalise une sévérité OSV/GHSA → CRITICAL/HIGH/MEDIUM/LOW/UNKNOWN."""
    if not value:
        return "UNKNOWN"
    upper = value.strip().upper()
    if upper in ("MODERATE",):
        return "MEDIUM"
    return upper if upper in _SEVERITY_RANK else "UNKNOWN"


async def real_deps_provider() -> list[Dependency]:
    """``uv export`` (sans hashes / sans le projet), parsé en dépendances."""
    proc = await asyncio.create_subprocess_exec(
        "uv",
        "export",
        "--format",
        "requirements-txt",
        "--no-hashes",
        "--no-emit-project",
        cwd=str(REPO_ROOT),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(f"uv export a échoué : {stderr.decode('utf-8', 'replace')[:200]}")
    return parse_requirements(stdout.decode("utf-8", "replace"))


async def real_osv_query(deps: list[Dependency]) -> list[Vulnerability]:
    """Interroge OSV.dev (batch + détail par vuln) pour les deps fournies."""
    if not deps:
        return []
    queries = [
        {"package": {"name": d.name, "ecosystem": "PyPI"}, "version": d.version} for d in deps
    ]
    out: list[Vulnerability] = []
    async with httpx.AsyncClient(timeout=OSV_TIMEOUT) as client:
        resp = await client.post(OSV_BATCH_URL, json={"queries": queries})
        resp.raise_for_status()
        data = resp.json()
        results = data.get("results", []) if isinstance(data, dict) else []
        for dep, result in zip(deps, results, strict=False):
            if not isinstance(result, dict):
                continue
            for vuln in result.get("vulns", []) or []:
                if not isinstance(vuln, dict):
                    continue
                vuln_id = str(vuln.get("id", "?"))
                detail = await client.get(f"{OSV_VULN_URL}/{vuln_id}")
                raw_body = detail.json() if detail.status_code == 200 else {}
                body = raw_body if isinstance(raw_body, dict) else {}
                db_specific = body.get("database_specific")
                sev = normalize_severity(
                    db_specific.get("severity") if isinstance(db_specific, dict) else None
                )
                out.append(
                    Vulnerability(
                        dep.name, dep.version, vuln_id, sev, str(body.get("summary", ""))[:160]
                    )
                )
    return out


def build_report(n_deps: int, vulns: list[Vulnerability]) -> SreReport:
    counts = {sev: sum(1 for v in vulns if v.severity == sev) for sev in _SEVERITY_RANK}
    has_alert = any(v.severity in SEVERITY_ALERT for v in vulns)
    has_warn = any(v.severity in SEVERITY_WARN for v in vulns)
    severity: Severity = "red" if has_alert else ("yellow" if has_warn else "green")
    summary = (
        f"{counts['CRITICAL']} CRITICAL · {counts['HIGH']} HIGH · {counts['MEDIUM']} MEDIUM · "
        f"{counts['LOW']} LOW · {counts['UNKNOWN']} UNKNOWN (sur {n_deps} deps)"
    )
    detail = "\n".join(
        f"- {v.dep_name} {v.dep_version} : {v.vuln_id} [{v.severity}] {v.summary}"
        for v in sorted(vulns, key=lambda x: -_SEVERITY_RANK[x.severity])[:20]
    )
    return SreReport(severity, summary, detail)


class DependencyAuditorScript(BaseSreScript):
    """Scanne les dépendances et alerte sur les CVE HIGH/CRITICAL."""

    name = "dependency_auditor"

    def __init__(
        self,
        *,
        poles_root: Path = POLES_DIR,
        deps_provider: DepsProvider | None = None,
        osv_query: OsvQuery | None = None,
    ) -> None:
        super().__init__(poles_root=poles_root)
        self._deps_provider = deps_provider or real_deps_provider
        self._osv_query = osv_query or real_osv_query

    async def check(self) -> SreReport:
        try:
            deps = await self._deps_provider()
            vulns = await self._osv_query(deps)
        except (OSError, RuntimeError, ValueError, httpx.HTTPError) as exc:
            # ValueError couvre json.JSONDecodeError (réponse OSV 200 mais corps
            # non-JSON / tronqué) ⇒ on dégrade en jaune (« audit impossible »),
            # jamais de rouge sur un hoquet réseau transitoire.
            logger.warning(f"dependency_auditor — audit impossible : {exc}")
            return SreReport("yellow", f"Audit des dépendances impossible : {type(exc).__name__}")
        return build_report(len(deps), vulns)


__all__ = [
    "SEVERITY_ALERT",
    "SEVERITY_WARN",
    "Dependency",
    "DependencyAuditorScript",
    "DepsProvider",
    "OsvQuery",
    "Vulnerability",
    "build_report",
    "normalize_severity",
    "parse_requirements",
    "real_deps_provider",
    "real_osv_query",
]
