"""BreachWatcher — Threat Intel (P22.D Veille Sprint 6).

Croise les breaches publics récents (flux RSS CERT-FR + API HIBP
``/breaches``) avec le carnet client/prospect Argos
(``data/crm/customers.yaml``). Si un domaine client apparaît dans une
fuite récente, on alerte le founder pour démarrer un email proactif
("on a détecté votre domaine dans la fuite X, voici nos recommandations").

Politique anti-spam :
- **Silence** Discord si aucun croisement
- **Embed jaune** si ≥1 client apparaît dans une fuite "Verified" sans
  source primaire à risque
- **Embed rouge** si ≥1 client apparaît dans une fuite avec mots-clés
  critiques (``passwords``, ``credentials``, ``ssh``, ``api_keys``)

Garde-fous éthiques :
- Aucun téléchargement de dump réel — on lit seulement les metadata
  publiées (titre, date, classes de données impactées)
- Le résultat reste local (data/breaches/last_run.json) — jamais
  partagé en dehors du founder pour éviter toute fuite d'info "ce
  client est victime"

Cf. plan ``docs/ARGOS_OPS_PLAN.md`` Annexe D § 8 Veille, Sprint 6.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Final

import yaml
from loguru import logger

from argos_ops.agents._fetcher_base import fetch
from argos_ops.agents._watcher_base import color_title, emit_alert_or_silence
from argos_ops.agents.base import BaseAgent, RunResult
from argos_ops.config import REPO_ROOT
from argos_ops.notifications.discord import GREEN, RED, YELLOW, Embed, EmbedField

CERT_FR_RSS = "https://www.cert.ssi.gouv.fr/alerte/feed/"
HIBP_BREACHES = "https://haveibeenpwned.com/api/v3/breaches"
SERVICE_NAME = "breach-watcher"
DEFAULT_CUSTOMERS_PATH: Path = REPO_ROOT / "data" / "crm" / "customers.yaml"
DEFAULT_LAST_RUN_PATH: Path = REPO_ROOT / "data" / "breaches" / "last_run.json"
DEFAULT_LOOKBACK_DAYS = 30

CRITICAL_KEYWORDS: Final[frozenset[str]] = frozenset(
    {"password", "passwords", "credential", "credentials", "ssh", "api_key", "api_keys"}
)


@dataclass(frozen=True)
class BreachEvent:
    """Événement de breach publié — agnostique de la source."""

    source: str  # "CERT-FR" | "HIBP"
    title: str
    published_at: datetime | None
    summary: str  # texte court qui peut contenir les domaines / keywords
    affected_domain: str | None  # extrait depuis title/summary par regex simple


@dataclass(frozen=True)
class Customer:
    name: str
    domain: str


@dataclass(frozen=True)
class BreachMatch:
    """Croisement breach ↔ client."""

    event: BreachEvent
    customer: Customer
    is_critical: bool


@dataclass(frozen=True)
class BreachReport:
    matches: list[BreachMatch]
    total_breaches_scanned: int
    should_alert: bool
    alert_color: int
    summary: str


# =============================================================================
# Config
# =============================================================================
def load_customers(path: Path = DEFAULT_CUSTOMERS_PATH) -> list[Customer]:
    """Lit ``customers.yaml``. Fichier absent → liste vide silencieuse."""
    if not path.exists():
        return []
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    entries = raw.get("customers", [])
    out: list[Customer] = []
    for entry in entries:
        name = entry.get("name")
        domain = entry.get("domain")
        if not name or not domain:
            continue
        out.append(Customer(name=str(name), domain=str(domain).lower().strip()))
    return out


# =============================================================================
# Sources
# =============================================================================
_DOMAIN_RE = re.compile(r"[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+")


def _extract_domain(text: str) -> str | None:
    match = _DOMAIN_RE.search(text)
    return match.group(0).lower() if match else None


async def fetch_cert_fr() -> list[BreachEvent]:
    """Parse le flux RSS CERT-FR via feedparser."""
    try:
        import feedparser  # type: ignore[import-untyped]
    except ImportError:
        logger.warning("BreachWatcher — feedparser indisponible, skip CERT-FR")
        return []
    response = await fetch(CERT_FR_RSS, service=SERVICE_NAME)
    parsed = feedparser.parse(response.body)
    events: list[BreachEvent] = []
    for entry in parsed.entries:
        title = str(entry.get("title", ""))
        summary = str(entry.get("summary", ""))[:500]
        published_at: datetime | None = None
        if hasattr(entry, "published_parsed") and entry.published_parsed:
            from time import mktime

            published_at = datetime.fromtimestamp(mktime(entry.published_parsed), UTC)
        events.append(
            BreachEvent(
                source="CERT-FR",
                title=title,
                published_at=published_at,
                summary=summary,
                affected_domain=_extract_domain(f"{title} {summary}"),
            )
        )
    return events


async def fetch_hibp() -> list[BreachEvent]:
    """API publique HIBP ``/breaches`` — pas d'auth nécessaire pour la liste."""
    response = await fetch(HIBP_BREACHES, service=SERVICE_NAME)
    try:
        payload = json.loads(response.body)
    except json.JSONDecodeError as exc:
        logger.warning(f"BreachWatcher — HIBP payload invalide: {exc}")
        return []
    events: list[BreachEvent] = []
    for raw in payload:
        breach_date = raw.get("BreachDate")
        try:
            published_at = (
                datetime.strptime(breach_date, "%Y-%m-%d").replace(tzinfo=UTC)
                if breach_date
                else None
            )
        except ValueError:
            published_at = None
        domain = str(raw.get("Domain") or "").lower() or None
        data_classes = raw.get("DataClasses") or []
        summary = ", ".join(str(c).lower() for c in data_classes)[:500]
        events.append(
            BreachEvent(
                source="HIBP",
                title=str(raw.get("Name") or "<unknown>"),
                published_at=published_at,
                summary=summary,
                affected_domain=domain,
            )
        )
    return events


# =============================================================================
# Crossing
# =============================================================================
def _is_critical(event: BreachEvent) -> bool:
    haystack = f"{event.title} {event.summary}".lower()
    return any(kw in haystack for kw in CRITICAL_KEYWORDS)


def cross_with_customers(
    events: list[BreachEvent],
    customers: list[Customer],
    *,
    now: datetime | None = None,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
) -> list[BreachMatch]:
    """Renvoie les croisements breach ↔ client sur la fenêtre lookback."""
    now = now or datetime.now(UTC)
    cutoff = now - timedelta(days=lookback_days)
    customers_by_domain = {c.domain: c for c in customers}

    matches: list[BreachMatch] = []
    for event in events:
        if event.published_at and event.published_at < cutoff:
            continue
        if not event.affected_domain:
            continue
        customer = customers_by_domain.get(event.affected_domain)
        if customer is None:
            continue
        matches.append(
            BreachMatch(event=event, customer=customer, is_critical=_is_critical(event))
        )
    return matches


def build_report(
    matches: list[BreachMatch], total_breaches: int
) -> BreachReport:
    if not matches:
        return BreachReport(
            matches=[],
            total_breaches_scanned=total_breaches,
            should_alert=False,
            alert_color=GREEN,
            summary=f"0 client touché (sur {total_breaches} breaches scannés)",
        )

    has_critical = any(m.is_critical for m in matches)
    alert_color = RED if has_critical else YELLOW
    summary = (
        f"{len(matches)} client(s) touché(s) "
        f"({sum(1 for m in matches if m.is_critical)} critique[s])"
    )
    return BreachReport(
        matches=matches,
        total_breaches_scanned=total_breaches,
        should_alert=True,
        alert_color=alert_color,
        summary=summary,
    )


def build_breach_embed(report: BreachReport, *, now: datetime | None = None) -> Embed:
    now = now or datetime.now(UTC)
    fields = [
        EmbedField(
            name=f"{'[CRIT]' if match.is_critical else '[WARN]'} {match.customer.name}",
            value=f"{match.event.source} · {match.event.title}\n{match.event.summary[:300]}",
            inline=False,
        )
        for match in report.matches[:10]
    ]
    title_status = color_title(report.alert_color, green=GREEN, yellow=YELLOW, red=RED)
    return Embed(
        title=f"BreachWatcher — {title_status}",
        description=report.summary,
        color=report.alert_color,
        fields=fields,
        footer="Argos Ops • BreachWatcher",
        timestamp=now.isoformat(),
    )


# =============================================================================
# Persistence
# =============================================================================
def save_last_run(
    report: BreachReport, *, path: Path = DEFAULT_LAST_RUN_PATH
) -> None:
    """Sauvegarde le dernier run pour audit / digest matinal."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "ran_at": datetime.now(UTC).isoformat(),
        "total_breaches": report.total_breaches_scanned,
        "matches": [
            {
                "customer": m.customer.name,
                "domain": m.customer.domain,
                "source": m.event.source,
                "title": m.event.title,
                "is_critical": m.is_critical,
            }
            for m in report.matches
        ],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


class BreachWatcher(BaseAgent):
    """Threat Intel — croise breaches publics avec clients Argos."""

    name = "BreachWatcher"
    command = "/run-breach-watch"
    breaker_name = None
    ai_act_risk_class = "minimal"

    def __init__(
        self,
        *,
        customers_path: Path = DEFAULT_CUSTOMERS_PATH,
        last_run_path: Path = DEFAULT_LAST_RUN_PATH,
        lookback_days: int = DEFAULT_LOOKBACK_DAYS,
    ) -> None:
        self._customers_path = customers_path
        self._last_run_path = last_run_path
        self._lookback_days = lookback_days

    async def run(self) -> RunResult:
        customers = load_customers(self._customers_path)
        if not customers:
            logger.info(f"BreachWatcher — aucun client déclaré ({self._customers_path})")
            return RunResult(
                status="success",
                output_summary="silence (aucun client)",
                extras={"alerted": False, "summary": "0 customers"},
            )

        cert_fr = await fetch_cert_fr()
        hibp = await fetch_hibp()
        events = cert_fr + hibp
        matches = cross_with_customers(
            events, customers, lookback_days=self._lookback_days
        )
        report = build_report(matches, total_breaches=len(events))
        save_last_run(report, path=self._last_run_path)
        return await emit_alert_or_silence(
            report, embed_builder=build_breach_embed, agent_name=self.name
        )


__all__ = [
    "CERT_FR_RSS",
    "CRITICAL_KEYWORDS",
    "DEFAULT_CUSTOMERS_PATH",
    "DEFAULT_LAST_RUN_PATH",
    "DEFAULT_LOOKBACK_DAYS",
    "HIBP_BREACHES",
    "SERVICE_NAME",
    "BreachEvent",
    "BreachMatch",
    "BreachReport",
    "BreachWatcher",
    "Customer",
    "build_breach_embed",
    "build_report",
    "cross_with_customers",
    "fetch_cert_fr",
    "fetch_hibp",
    "load_customers",
    "save_last_run",
]
