"""``DarkWebMonitorScript`` — domaines clients dans les breaches HIBP (Veille v2).

Porté depuis ``argos_ops.agents.dw_monitor`` (legacy). Bras déterministe (MVP) :

1. lit les domaines clients depuis ``data/crm/customers.yaml`` ;
2. interroge la liste publique des breaches HIBP (via :func:`fetch`, cache 24h) ;
3. croise domaines x breaches, filtre les **nouveaux** hits (dédup fichier) ;
4. écrit chaque nouveau hit dans **sa propre mémoire de pôle** (``kind="darkweb"``)
   et persiste l'état de dédup (``seen_hits.json``).

Pas de Discord, pas de DB, pas de LLM (D-017) : le :class:`VeilleAgent` lit cette
mémoire et agit. Idempotent : un hit re-détecté a le même corps (donc même fait,
le socle :func:`argos_ops.poles.memory.write_memory` déduplique par hash) et son
``_hit_id`` reste dans ``seen_hits.json``.

Garde-fous éthiques portés du legacy : aucune liste de comptes ne quitte la
machine - seul le compte agrégé par domaine est mémorisé.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import yaml
from loguru import logger

from argos_ops.agents._fetcher_base import fetch
from argos_ops.config import REPO_ROOT
from argos_ops.poles.base import BaseScript, ScriptResult
from argos_ops.poles.config import POLES_DIR

SERVICE_NAME = "dw-monitor"
HIBP_DOMAIN_ENDPOINT = "https://haveibeenpwned.com/api/v3/breaches"  # liste statique
DEFAULT_CUSTOMERS_PATH: Path = REPO_ROOT / "data" / "crm" / "customers.yaml"
DEFAULT_SEEN_PATH: Path = REPO_ROOT / "data" / "darkweb" / "seen_hits.json"


@dataclass(frozen=True)
class DomainHit:
    """Apparition d'un domaine prospect dans la base HIBP."""

    customer_name: str
    domain: str
    breach_name: str
    pwn_count: int  # nombre d'emails du domaine touchés (estimation)
    breach_date: str  # YYYY-MM-DD


def _hit_id(hit: DomainHit) -> str:
    return f"{hit.domain}::{hit.breach_name}"


# =============================================================================
# Config
# =============================================================================
def load_domains(path: Path = DEFAULT_CUSTOMERS_PATH) -> list[tuple[str, str]]:
    """Renvoie ``[(customer_name, domain), ...]`` depuis ``customers.yaml``."""
    if not path.exists():
        return []
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    out: list[tuple[str, str]] = []
    for entry in raw.get("customers", []):
        name = entry.get("name")
        domain = entry.get("domain")
        if not name or not domain:
            continue
        out.append((str(name), str(domain).lower().strip()))
    return out


# =============================================================================
# Seen hits (dedup)
# =============================================================================
def load_seen_hits(path: Path = DEFAULT_SEEN_PATH) -> set[str]:
    if not path.exists():
        return set()
    try:
        return set(json.loads(path.read_text(encoding="utf-8")).get("seen", []))
    except (json.JSONDecodeError, ValueError) as exc:
        logger.warning(f"DarkWebMonitor seen_hits corrompu: {exc}")
        return set()


def save_seen_hits(seen: set[str], *, path: Path = DEFAULT_SEEN_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"seen": sorted(seen), "saved_at": datetime.now(UTC).isoformat()}),
        encoding="utf-8",
    )


# =============================================================================
# HIBP query
# =============================================================================
async def fetch_hibp_breaches() -> list[dict[str, str | int]]:
    """Renvoie la liste publique des breaches HIBP (sans auth)."""
    response = await fetch(HIBP_DOMAIN_ENDPOINT, service=SERVICE_NAME)
    try:
        payload = json.loads(response.body)
    except json.JSONDecodeError as exc:
        logger.warning(f"DarkWebMonitor - payload HIBP invalide: {exc}")
        return []
    if not isinstance(payload, list):
        return []
    return payload


def cross_domains_with_breaches(
    domains: list[tuple[str, str]], breaches: list[dict[str, str | int]]
) -> list[DomainHit]:
    """Croise les domaines clients avec la liste de breaches publiques."""
    by_domain: dict[str, list[dict[str, str | int]]] = {}
    for breach in breaches:
        raw_domain = str(breach.get("Domain") or "").lower().strip()
        if not raw_domain:
            continue
        by_domain.setdefault(raw_domain, []).append(breach)

    hits: list[DomainHit] = []
    for customer_name, domain in domains:
        for breach in by_domain.get(domain, []):
            pwn_count_raw = breach.get("PwnCount") or 0
            pwn_count = int(pwn_count_raw) if isinstance(pwn_count_raw, int | str) else 0
            hits.append(
                DomainHit(
                    customer_name=customer_name,
                    domain=domain,
                    breach_name=str(breach.get("Name") or "<unknown>"),
                    pwn_count=pwn_count,
                    breach_date=str(breach.get("BreachDate") or ""),
                )
            )
    return hits


class DarkWebMonitorScript(BaseScript):
    """Repère les domaines clients pwned (HIBP) et les mémorise (``kind="darkweb"``)."""

    pole = "veille"
    name = "darkweb_monitor"

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
        domains = load_domains(self._customers_path)
        if not domains:
            return ScriptResult(
                status="success",
                summary="aucun domaine déclaré",
                written=[],
            )

        breaches = await fetch_hibp_breaches()
        hits = cross_domains_with_breaches(domains, breaches)

        seen = load_seen_hits(self._seen_path)
        new_hits = [h for h in hits if _hit_id(h) not in seen]
        seen.update(_hit_id(h) for h in hits)
        save_seen_hits(seen, path=self._seen_path)

        written = []
        for hit in new_hits:
            record = await self.write_memory(
                f"Domaine {hit.domain} ({hit.customer_name}) dans le breach "
                f"{hit.breach_name} ({hit.breach_date}) ~{hit.pwn_count} comptes",
                kind="darkweb",
                tags=("darkweb",),
                important=False,
                source=HIBP_DOMAIN_ENDPOINT,
            )
            written.append(record)

        total_pwned = sum(h.pwn_count for h in new_hits)
        return ScriptResult(
            status="success",
            summary=(
                f"{len(new_hits)} nouveau(x) hit(s) sur {len(domains)} domaine(s) "
                f"- ~{total_pwned} comptes exposés"
            ),
            written=written,
        )


__all__ = [
    "DEFAULT_CUSTOMERS_PATH",
    "DEFAULT_SEEN_PATH",
    "HIBP_DOMAIN_ENDPOINT",
    "SERVICE_NAME",
    "DarkWebMonitorScript",
    "DomainHit",
    "cross_domains_with_breaches",
    "fetch_hibp_breaches",
    "load_domains",
    "load_seen_hits",
    "save_seen_hits",
]
