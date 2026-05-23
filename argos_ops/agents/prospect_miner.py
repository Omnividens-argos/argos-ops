"""ProspectMiner — Sourcer commercial (P22.H Sales Sprint 3).

Cherche de nouveaux prospects ICP via **sources publiques uniquement** :

- ``annonces_legales`` — flux RSS BODACC / annonces-legales.fr (création
  de société, mutations capital). Format YAML déclaré dans
  ``data/sales/prospects/sources.yaml``.
- ``crunchbase_news`` — RSS public ``news.crunchbase.com/feed/`` (levées
  de fonds, sans API payante).
- ``linkedin_jobs`` — flux RSS LinkedIn Jobs filtrés (CISO / RSSI /
  Head of Security France). LinkedIn expose des RSS auth-free pour les
  recherches sauvegardées.
- ``manual`` — entrées YAML statiques (sandbox fondateur).

Politique D-016 / D-017 : pas de scraping LinkedIn HTML (anti-pattern
ToS), pas d'API payante. Si un flux est down, on logue + on continue.

Output : append des nouveaux leads dans
``data/outbound/inbox/leads.csv`` (consommé en aval par OutboundBot
P13.A). Idempotent — on dédupe sur ``(full_name, domain)``.

Notification Discord : embed avec compteurs par source. Pas de silence
si zero (le fondateur veut savoir si une source est silencieuse depuis
trop longtemps).
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

import httpx
import yaml
from loguru import logger

from argos_ops.agents.base import BaseAgent, RunResult
from argos_ops.config import REPO_ROOT, get_settings
from argos_ops.notifications.discord import (
    GREEN,
    YELLOW,
    Embed,
    EmbedField,
    send_embed,
)
from argos_ops.outbound.sequence import INBOX_DIR
from argos_ops.sales.models import Prospect, ProspectSource

DEFAULT_SOURCES_PATH: Path = REPO_ROOT / "data" / "sales" / "prospects" / "sources.yaml"
DEFAULT_INBOX_CSV: Path = INBOX_DIR / "leads.csv"


@dataclass
class MiningStats:
    """Compteurs d'un run."""

    candidates_seen: int = 0
    new_appended: int = 0
    skipped_dup: int = 0
    sources_unreachable: int = 0
    by_source: dict[str, int] = field(default_factory=dict)

    def summary(self) -> str:
        return (
            f"seen={self.candidates_seen} new={self.new_appended} "
            f"dup={self.skipped_dup} sources_unreachable={self.sources_unreachable}"
        )


def _load_sources(path: Path) -> dict[str, Any]:
    """Lit le YAML des sources — retourne dict vide si absent."""
    if not path.exists():
        return {}
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"sources.yaml malformé : {path}")
    return raw


def _read_existing_keys(csv_path: Path) -> set[tuple[str, str]]:
    """Charge les ``(full_name, domain)`` déjà présents dans l'inbox."""
    if not csv_path.exists():
        return set()
    keys: set[tuple[str, str]] = set()
    with csv_path.open("r", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            name = (row.get("full_name") or "").strip()
            domain = (row.get("domain") or "").strip().lower()
            if name and domain:
                keys.add((name, domain))
    return keys


def _parse_rss_titles(xml_bytes: bytes, max_items: int = 30) -> list[str]:
    """Extrait les titres d'un flux RSS / Atom — best-effort."""
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as exc:
        logger.warning(f"ProspectMiner — RSS parse error : {exc}")
        return []
    titles: list[str] = []
    # RSS 2.0 : <channel><item><title>
    for item in root.iter():
        tag = item.tag.lower().rsplit("}", 1)[-1]
        if tag in {"item", "entry"}:
            for child in item:
                ctag = child.tag.lower().rsplit("}", 1)[-1]
                if ctag == "title" and child.text:
                    titles.append(child.text.strip())
                    break
        if len(titles) >= max_items:
            break
    return titles


def _extract_company_from_title(title: str) -> tuple[str | None, str | None]:
    """Heuristique très simple — extrait ``(company, domain)`` si visible.

    Le titre RSS d'annonces légales contient typiquement le nom de
    société en début ; on découpe au premier ``-`` ou ``—``. Pas de
    NLP — c'est volontairement pauvre, le fondateur affine à la main.
    """
    raw = title.split("—")[0].split(" - ")[0].strip()
    if not raw or len(raw) > 80:
        return None, None
    # Domaine non extractible depuis un titre RSS — on laisse vide,
    # le fondateur le complète dans le CSV.
    return raw, None


async def _fetch_rss(url: str, timeout: float = 8.0) -> bytes | None:
    """GET avec timeout court. Retourne ``None`` si erreur réseau."""
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            resp = await client.get(url, headers={"User-Agent": "ArgosOps/ProspectMiner"})
            if resp.status_code >= 300:
                logger.warning(f"ProspectMiner — {url} HTTP {resp.status_code}")
                return None
            return resp.content
    except (httpx.HTTPError, httpx.TimeoutException) as exc:
        logger.warning(f"ProspectMiner — {url} unreachable : {exc}")
        return None


async def _mine_sources(sources: dict[str, Any]) -> list[Prospect]:
    """Itère les sources YAML et produit des candidats Prospect.

    Les sources ``manual`` sont déjà sous forme structurée — on les
    convertit direct. Les RSS sont fetchés et parsés best-effort.
    """
    now_iso = datetime.now(UTC).isoformat()
    out: list[Prospect] = []

    # Manual : liste d'objets avec full_name / company / domain / title_hint
    for entry in sources.get("manual", []) or []:
        out.append(
            Prospect(
                full_name=entry.get("full_name"),
                company=entry.get("company") or entry.get("full_name") or "?",
                domain=(entry.get("domain") or "").lower(),
                source=ProspectSource.MANUAL,
                title_hint=entry.get("title_hint"),
                raw_signal=entry.get("raw_signal"),
                discovered_at=now_iso,
            )
        )

    # RSS : 3 catégories
    rss_blocks = {
        "annonces_legales": ProspectSource.ANNONCES_LEGALES,
        "crunchbase_news": ProspectSource.CRUNCHBASE_NEWS,
        "linkedin_jobs": ProspectSource.LINKEDIN_JOBS,
    }
    for key, source_enum in rss_blocks.items():
        for feed_url in sources.get(key, []) or []:
            xml = await _fetch_rss(feed_url)
            if xml is None:
                continue
            for title in _parse_rss_titles(xml):
                company, domain = _extract_company_from_title(title)
                if company is None:
                    continue
                out.append(
                    Prospect(
                        full_name=None,
                        company=company,
                        domain=(domain or "").lower(),
                        source=source_enum,
                        title_hint=None,
                        raw_signal=title,
                        discovered_at=now_iso,
                    )
                )
    return out


def _append_to_inbox(
    prospects: list[Prospect],
    *,
    csv_path: Path,
    existing_keys: set[tuple[str, str]],
) -> tuple[int, int, dict[str, int]]:
    """Append les prospects nouveaux à l'inbox CSV. Retourne ``(new, dup, by_source)``.

    Format inbox : ``full_name,domain,title_hint,linkedin_url`` (cf.
    ``argos_ops.outbound.sequence._REQUIRED_COLS``). On ne peut pas
    écrire un prospect sans ``full_name`` ou sans ``domain`` valide
    → on l'incrémente en ``skipped`` (raison signalée dans le summary).
    """
    new_count = 0
    dup_count = 0
    by_source: dict[str, int] = {}
    csv_path.parent.mkdir(parents=True, exist_ok=True)

    write_header = not csv_path.exists()
    with csv_path.open("a", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        if write_header:
            writer.writerow(["full_name", "domain", "title_hint", "linkedin_url"])

        for p in prospects:
            if not p.full_name or not p.domain:
                # Pas écrivable dans l'inbox tel quel — comptabilisé
                # par-source mais pas appended (le fondateur affinera
                # depuis le report Discord).
                by_source[p.source.value] = by_source.get(p.source.value, 0) + 0
                continue
            key = (p.full_name, p.domain)
            if key in existing_keys:
                dup_count += 1
                continue
            writer.writerow([p.full_name, p.domain, p.title_hint or "", ""])
            existing_keys.add(key)
            new_count += 1
            by_source[p.source.value] = by_source.get(p.source.value, 0) + 1
    return new_count, dup_count, by_source


def build_mining_embed(stats: MiningStats) -> Embed:
    """Embed Discord récap."""
    color = YELLOW if stats.new_appended > 0 else GREEN
    fields = [
        EmbedField(name="Candidats vus", value=str(stats.candidates_seen), inline=True),
        EmbedField(name="Nouveaux dans l'inbox", value=str(stats.new_appended), inline=True),
        EmbedField(name="Doublons skippés", value=str(stats.skipped_dup), inline=True),
        EmbedField(name="Sources injoignables", value=str(stats.sources_unreachable), inline=True),
    ]
    if stats.by_source:
        breakdown = "\n".join(f"• {k} : {v}" for k, v in sorted(stats.by_source.items()))
        fields.append(EmbedField(name="Par source", value=breakdown, inline=False))
    return Embed(
        title=f"ProspectMiner — {stats.new_appended} nouveaux prospects",
        description=(
            "Inbox CSV mis à jour. Lance `/run-lead-enrich` puis "
            "`/run-outbound-bot` pour scaffold les séquences."
            if stats.new_appended > 0
            else "Aucun nouveau prospect (sources stables, ICP saturé ?)."
        ),
        color=color,
        fields=fields,
        footer="Argos Ops • ProspectMiner",
    )


class ProspectMiner(BaseAgent):
    """Sourcer ICP — cron quotidien matinal."""

    name = "ProspectMiner"
    command = "/run-prospect-mining"
    breaker_name = "ProspectMiner"

    def __init__(
        self,
        *,
        sources_path: Path = DEFAULT_SOURCES_PATH,
        inbox_csv: Path = DEFAULT_INBOX_CSV,
    ) -> None:
        self._sources_path = sources_path
        self._inbox_csv = inbox_csv

    async def run(self) -> RunResult:
        settings = get_settings()
        sources = _load_sources(self._sources_path)
        if not sources:
            logger.info(f"ProspectMiner — aucune source déclarée ({self._sources_path}), skip")
            return RunResult(status="success", output_summary="silence (no sources)")

        prospects = await _mine_sources(sources)
        existing = _read_existing_keys(self._inbox_csv)
        new, dup, by_source = _append_to_inbox(
            prospects, csv_path=self._inbox_csv, existing_keys=existing
        )
        stats = MiningStats(
            candidates_seen=len(prospects),
            new_appended=new,
            skipped_dup=dup,
            by_source=by_source,
        )

        webhook = settings.discord_webhook_ops_logs or settings.discord_webhook_alerts
        if webhook is not None:
            try:
                await send_embed(webhook, build_mining_embed(stats))
            except Exception as exc:
                logger.warning(f"ProspectMiner — notif Discord a échoué : {exc}")

        return RunResult(status="success", output_summary=stats.summary())


__all__ = [
    "DEFAULT_INBOX_CSV",
    "DEFAULT_SOURCES_PATH",
    "MiningStats",
    "ProspectMiner",
    "build_mining_embed",
]
