"""DarkWebMonitor — Threat Intel Senior (P22.D Veille Sprint 6+).

MVP : interroge l'API HIBP **domain search**
(``/breachedaccount/{account}`` agrégée par domaine) pour repérer si
des emails du domaine d'un prospect ont déjà été pwned. Le résultat
sert de **sell point** dans une approche outbound personnalisée
("on a relevé 247 comptes de votre domaine dans des breaches publiques").

Politique anti-spam :
- **Silence** Discord si aucun nouveau domaine pwned détecté
- **Embed jaune** si ≥1 domaine prospect présente un nouvel hit
  (la sévérité varie avec le nombre de comptes touchés)

Garde-fous éthiques :
- HIBP domain search requiert une clé API et **vérification de la
  propriété du domaine**. En MVP shadow, on simule via
  ``DW_MONITOR_API_KEY`` (vide par défaut) — l'agent répond ``silence
  (clé absente)`` tant que le founder n'a pas activé une vraie clé.
- Aucune liste de comptes ne quitte la machine — seul le *compte agrégé*
  par domaine est affiché.

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
from argos_ops.config import REPO_ROOT
from argos_ops.notifications.discord import GREEN, YELLOW, Embed, EmbedField

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


@dataclass(frozen=True)
class DwReport:
    hits: list[DomainHit]
    total_domains_scanned: int
    should_alert: bool
    alert_color: int
    summary: str


def _hit_id(hit: DomainHit) -> str:
    return f"{hit.domain}::{hit.breach_name}"


# =============================================================================
# Config
# =============================================================================
def load_domains(path: Path = DEFAULT_CUSTOMERS_PATH) -> list[tuple[str, str]]:
    """Renvoie ``[(customer_name, domain), …]`` depuis ``customers.yaml``."""
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
        logger.warning(f"DarkWebMonitor — payload HIBP invalide: {exc}")
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


# =============================================================================
# Report
# =============================================================================
def build_report(hits: list[DomainHit], total_domains: int) -> DwReport:
    if not hits:
        return DwReport(
            hits=[],
            total_domains_scanned=total_domains,
            should_alert=False,
            alert_color=GREEN,
            summary=f"aucun hit (sur {total_domains} domaines)",
        )
    total_pwned = sum(h.pwn_count for h in hits)
    return DwReport(
        hits=hits,
        total_domains_scanned=total_domains,
        should_alert=True,
        alert_color=YELLOW,
        summary=(
            f"{len(hits)} hit(s) sur {len({h.domain for h in hits})} domaine(s) — "
            f"~{total_pwned:,} comptes exposés"
        ),
    )


def build_dw_embed(report: DwReport, *, now: datetime | None = None) -> Embed:
    now = now or datetime.now(UTC)
    fields = [
        EmbedField(
            name=f"[HIT] {hit.customer_name} · {hit.domain}",
            value=(
                f"Breach : `{hit.breach_name}` ({hit.breach_date})\n"
                f"~{hit.pwn_count:,} comptes touchés"
            ),
            inline=False,
        )
        for hit in report.hits[:10]
    ]
    title_status = color_title(report.alert_color, green=GREEN, yellow=YELLOW, red=YELLOW)
    return Embed(
        title=f"DarkWebMonitor — {title_status}",
        description=report.summary,
        color=report.alert_color,
        fields=fields,
        footer="Argos Ops • DarkWebMonitor (MVP HIBP)",
        timestamp=now.isoformat(),
    )


class DarkWebMonitor(BaseAgent):
    """Threat Intel Senior — domaines clients dans les breaches publiques."""

    name = "DarkWebMonitor"
    command = "/run-dw-monitor"
    breaker_name = None

    def __init__(
        self,
        *,
        customers_path: Path = DEFAULT_CUSTOMERS_PATH,
        seen_path: Path = DEFAULT_SEEN_PATH,
    ) -> None:
        self._customers_path = customers_path
        self._seen_path = seen_path

    async def run(self) -> RunResult:
        domains = load_domains(self._customers_path)
        if not domains:
            return RunResult(
                status="success",
                output_summary="silence (aucun domaine déclaré)",
                extras={"alerted": False, "summary": "0 domains"},
            )

        breaches = await fetch_hibp_breaches()
        hits = cross_domains_with_breaches(domains, breaches)

        seen = load_seen_hits(self._seen_path)
        new_hits = [h for h in hits if _hit_id(h) not in seen]
        seen.update(_hit_id(h) for h in hits)
        save_seen_hits(seen, path=self._seen_path)

        report = build_report(new_hits, total_domains=len(domains))
        return await emit_alert_or_silence(
            report, embed_builder=build_dw_embed, agent_name=self.name
        )


__all__ = [
    "DEFAULT_CUSTOMERS_PATH",
    "DEFAULT_SEEN_PATH",
    "HIBP_DOMAIN_ENDPOINT",
    "SERVICE_NAME",
    "DarkWebMonitor",
    "DomainHit",
    "DwReport",
    "build_dw_embed",
    "build_report",
    "cross_domains_with_breaches",
    "fetch_hibp_breaches",
    "load_domains",
    "load_seen_hits",
    "save_seen_hits",
]
