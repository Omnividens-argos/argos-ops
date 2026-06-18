"""``BreachWatcherScript`` — threat intel breaches publics x clients (Veille, archi v2).

Porté depuis ``argos_ops.agents.breach_watcher`` (legacy). Bras déterministe :

1. lit le carnet client/prospect Argos (``data/crm/customers.yaml``) ;
2. récupère les breaches publics récents (flux RSS CERT-FR + API HIBP
   ``/breaches``) via l'infra HTTP partagée :func:`argos_ops.agents._fetcher_base.fetch` ;
3. croise chaque breach avec un domaine client sur la fenetre lookback ;
4. écrit chaque croisement dans **sa propre mémoire de pôle** (``kind="breach"``).

Garde-fous éthiques (inchangés vs legacy) : aucun téléchargement de dump réel -
on ne lit que les metadata publiées (titre, date, classes de données). Le résultat
reste local : c'est le :class:`VeilleAgent` qui lit cette mémoire et agit. Pas de
Discord, pas de DB, pas de LLM (D-017).

Sévérité : un croisement critique (mots-clés ``passwords`` / ``credentials`` /
``ssh`` / ``api_keys``) est marqué ``important=True`` + tag ``critical`` ; sinon
tag ``warning``. Idempotent : un croisement re-détecté a le même corps ⇒ même fait
(le socle :func:`argos_ops.poles.memory.write_memory` déduplique par hash).
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
from argos_ops.config import REPO_ROOT
from argos_ops.poles.base import BaseScript, ScriptResult
from argos_ops.poles.config import POLES_DIR

CERT_FR_RSS = "https://www.cert.ssi.gouv.fr/alerte/feed/"
HIBP_BREACHES = "https://haveibeenpwned.com/api/v3/breaches"
SERVICE_NAME = "breach-watcher"
DEFAULT_CUSTOMERS_PATH: Path = REPO_ROOT / "data" / "crm" / "customers.yaml"
DEFAULT_LOOKBACK_DAYS = 30

CRITICAL_KEYWORDS: Final[frozenset[str]] = frozenset(
    {"password", "passwords", "credential", "credentials", "ssh", "api_key", "api_keys"}
)


@dataclass(frozen=True)
class BreachEvent:
    """Événement de breach publié - agnostique de la source."""

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
    """Croisement breach x client."""

    event: BreachEvent
    customer: Customer
    is_critical: bool


# =============================================================================
# Config
# =============================================================================
def load_customers(path: Path = DEFAULT_CUSTOMERS_PATH) -> list[Customer]:
    """Lit ``customers.yaml``. Fichier absent -> liste vide silencieuse."""
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
        logger.warning("BreachWatcher - feedparser indisponible, skip CERT-FR")
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
    """API publique HIBP ``/breaches`` - pas d'auth nécessaire pour la liste."""
    response = await fetch(HIBP_BREACHES, service=SERVICE_NAME)
    try:
        payload = json.loads(response.body)
    except json.JSONDecodeError as exc:
        logger.warning(f"BreachWatcher - HIBP payload invalide: {exc}")
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
    """Renvoie les croisements breach x client sur la fenetre lookback."""
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
        matches.append(BreachMatch(event=event, customer=customer, is_critical=_is_critical(event)))
    return matches


class BreachWatcherScript(BaseScript):
    """Croise les breaches publics avec les clients Argos et les mémorise."""

    pole = "veille"
    name = "breach_watcher"

    def __init__(
        self,
        *,
        poles_root: Path = POLES_DIR,
        customers_path: Path = DEFAULT_CUSTOMERS_PATH,
        lookback_days: int = DEFAULT_LOOKBACK_DAYS,
    ) -> None:
        super().__init__(poles_root=poles_root)
        self._customers_path = customers_path
        self._lookback_days = lookback_days

    async def run(self) -> ScriptResult:
        customers = load_customers(self._customers_path)
        if not customers:
            return ScriptResult(
                status="success",
                summary="0 client déclaré - silence",
                written=[],
            )

        cert_fr = await fetch_cert_fr()
        hibp = await fetch_hibp()
        events = cert_fr + hibp
        matches = cross_with_customers(events, customers, lookback_days=self._lookback_days)

        written = []
        for match in matches:
            event = match.event
            customer = match.customer
            tag = "critical" if match.is_critical else "warning"
            record = await self.write_memory(
                f"Client {customer.name} ({customer.domain}) dans la fuite "
                f"{event.source} : {event.title}",
                kind="breach",
                tags=("breach", tag),
                important=match.is_critical,
                source=event.source,
            )
            written.append(record)

        n_critical = sum(1 for m in matches if m.is_critical)
        return ScriptResult(
            status="success",
            summary=(
                f"{len(matches)} client(s) touché(s) ({n_critical} critique[s]) "
                f"sur {len(events)} breach(es) scanné(s)"
            ),
            written=written,
        )


__all__ = [
    "CERT_FR_RSS",
    "CRITICAL_KEYWORDS",
    "DEFAULT_CUSTOMERS_PATH",
    "DEFAULT_LOOKBACK_DAYS",
    "HIBP_BREACHES",
    "SERVICE_NAME",
    "BreachEvent",
    "BreachMatch",
    "BreachWatcherScript",
    "Customer",
    "cross_with_customers",
    "fetch_cert_fr",
    "fetch_hibp",
    "load_customers",
]
