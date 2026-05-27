"""BountyRadar — Bug Bounty Manager (P22.D Veille Sprint 6+).

Scrape les listings publics de programmes bug bounty (HackerOne et
YesWeHack) pour identifier de nouveaux programmes pertinents où
Argos pourrait se positionner, soit pour participer (recherche de
vulnérabilités sur la plateforme externe), soit pour cibler le
target-owner comme prospect ("vous gérez un programme bounty, on
peut compléter avec un scanner automatique").

Politique anti-spam :
- **Silence** Discord si aucun nouveau programme depuis le dernier run
- **Embed jaune** si ≥1 nouveau programme matche les filtres
  (pertinence sectorielle : SaaS BtoB, infosec, fintech)

Cet agent **n'a pas de slash command** (catalogue Annexe D) — il
tourne en cron pur (mensuel, peu d'impact, lecture longue).

Cf. plan ``docs/ARGOS_OPS_PLAN.md`` Annexe D § 8 Veille, Sprint 6+.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

import yaml
from loguru import logger

from argos_ops.agents._fetcher_base import fetch
from argos_ops.agents._watcher_base import color_title, emit_alert_or_silence
from argos_ops.agents.base import BaseAgent, RunResult
from argos_ops.config import REPO_ROOT
from argos_ops.notifications.discord import GREEN, YELLOW, Embed, EmbedField

SERVICE_NAME = "bounty-radar"
HACKERONE_PROGRAMS_URL = "https://hackerone.com/programs/search?query=type%3Ahackerone&sort=newest"
YESWEHACK_PROGRAMS_URL = "https://api.yeswehack.com/programs"
DEFAULT_FILTERS_PATH: Path = REPO_ROOT / "data" / "bounty" / "filters.yaml"
DEFAULT_SEEN_PATH: Path = REPO_ROOT / "data" / "bounty" / "seen_programs.json"

DEFAULT_KEYWORDS: Final[tuple[str, ...]] = (
    "saas",
    "fintech",
    "infosec",
    "cybersecurity",
    "api",
    "developer tools",
    "compliance",
)


@dataclass(frozen=True)
class BountyProgram:
    """Programme bounty repéré sur une plateforme publique."""

    platform: str  # "HackerOne" | "YesWeHack"
    handle: str  # slug unique sur la plateforme
    name: str
    url: str
    matched_keywords: list[str]


@dataclass(frozen=True)
class BountyReport:
    new_programs: list[BountyProgram]
    total_scanned: int
    should_alert: bool
    alert_color: int
    summary: str


# =============================================================================
# Filters config
# =============================================================================
def load_keywords(path: Path = DEFAULT_FILTERS_PATH) -> tuple[str, ...]:
    """Lit la liste des keywords pertinents (sectoriels + tech)."""
    if not path.exists():
        return DEFAULT_KEYWORDS
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    keywords = raw.get("keywords") or []
    cleaned = tuple(str(k).lower() for k in keywords if isinstance(k, str) and k.strip())
    return cleaned or DEFAULT_KEYWORDS


# =============================================================================
# Seen handles
# =============================================================================
def load_seen(path: Path = DEFAULT_SEEN_PATH) -> set[str]:
    if not path.exists():
        return set()
    try:
        return set(json.loads(path.read_text(encoding="utf-8")).get("seen", []))
    except (json.JSONDecodeError, ValueError) as exc:
        logger.warning(f"BountyRadar seen corrompu: {exc}")
        return set()


def save_seen(seen: set[str], *, path: Path = DEFAULT_SEEN_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"seen": sorted(seen), "saved_at": datetime.now(UTC).isoformat()}),
        encoding="utf-8",
    )


def _program_key(program: BountyProgram) -> str:
    return f"{program.platform}::{program.handle}"


# =============================================================================
# Platform fetchers
# =============================================================================
async def fetch_hackerone(keywords: tuple[str, ...]) -> list[BountyProgram]:
    """Scrape liste publique HackerOne (page HTML)."""
    try:
        response = await fetch(HACKERONE_PROGRAMS_URL, service=SERVICE_NAME)
    except Exception as exc:
        logger.warning(f"BountyRadar — HackerOne fetch échoué: {type(exc).__name__}: {exc}")
        return []
    return _parse_hackerone_html(response.body, keywords=keywords)


def _parse_hackerone_html(
    html: str, *, keywords: tuple[str, ...]
) -> list[BountyProgram]:
    """Extraction très naive — HackerOne HTML est rendu côté client (Next.js).

    En pratique on récupère le HTML pré-rendu et on cherche les
    ``href="/<handle>"`` puis le snippet associé. Pour un MVP, on retourne
    une liste vide tant que le scraping HTML n'a pas été tuné — l'agent
    tourne tout de même pour valider le pattern et le YesWeHack API.
    """
    if not html or not keywords:
        return []
    # Le rendu HackerOne est SPA — un MVP fiable demanderait Playwright
    # (lourd) ou leur API officielle (auth payante). On laisse la stub
    # vide en attendant un budget pour cette intégration spécifique.
    return []


async def fetch_yeswehack(keywords: tuple[str, ...]) -> list[BountyProgram]:
    """API publique YesWeHack (read-only, JSON, pas d'auth)."""
    try:
        response = await fetch(YESWEHACK_PROGRAMS_URL, service=SERVICE_NAME)
    except Exception as exc:
        logger.warning(f"BountyRadar — YesWeHack fetch échoué: {type(exc).__name__}: {exc}")
        return []
    try:
        payload = json.loads(response.body)
    except json.JSONDecodeError as exc:
        logger.warning(f"BountyRadar — YesWeHack payload invalide: {exc}")
        return []

    items = payload.get("items") if isinstance(payload, dict) else payload
    if not isinstance(items, list):
        return []

    out: list[BountyProgram] = []
    for raw in items:
        if not isinstance(raw, dict):
            continue
        slug = raw.get("slug") or raw.get("title")
        title = raw.get("title") or slug
        description = " ".join(
            str(raw.get(f) or "") for f in ("title", "description", "tags")
        ).lower()
        matched = [kw for kw in keywords if kw in description]
        if not matched:
            continue
        out.append(
            BountyProgram(
                platform="YesWeHack",
                handle=str(slug),
                name=str(title),
                url=f"https://yeswehack.com/programs/{slug}",
                matched_keywords=matched,
            )
        )
    return out


# =============================================================================
# Report
# =============================================================================
def build_report(
    new_programs: list[BountyProgram], total_scanned: int
) -> BountyReport:
    if not new_programs:
        return BountyReport(
            new_programs=[],
            total_scanned=total_scanned,
            should_alert=False,
            alert_color=GREEN,
            summary=f"aucun nouveau programme pertinent ({total_scanned} scannés)",
        )
    return BountyReport(
        new_programs=new_programs,
        total_scanned=total_scanned,
        should_alert=True,
        alert_color=YELLOW,
        summary=f"{len(new_programs)} nouveau(x) programme(s) bounty pertinent(s)",
    )


def build_bounty_embed(report: BountyReport, *, now: datetime | None = None) -> Embed:
    now = now or datetime.now(UTC)
    fields = [
        EmbedField(
            name=f"[{program.platform}] {program.name[:120]}",
            value=(
                f"keywords : `{', '.join(program.matched_keywords)}`\n"
                f"{program.url}"
            ),
            inline=False,
        )
        for program in report.new_programs[:10]
    ]
    title_status = color_title(report.alert_color, green=GREEN, yellow=YELLOW, red=YELLOW)
    return Embed(
        title=f"BountyRadar — {title_status}",
        description=report.summary,
        color=report.alert_color,
        fields=fields,
        footer="Argos Ops • BountyRadar",
        timestamp=now.isoformat(),
    )


class BountyRadar(BaseAgent):
    """Bug Bounty Manager — programmes bounty publics pertinents pour Argos."""

    name = "BountyRadar"
    command = None  # cron pur (mensuel)
    breaker_name = None
    ai_act_risk_class = "minimal"

    def __init__(
        self,
        *,
        filters_path: Path = DEFAULT_FILTERS_PATH,
        seen_path: Path = DEFAULT_SEEN_PATH,
    ) -> None:
        self._filters_path = filters_path
        self._seen_path = seen_path

    async def run(self) -> RunResult:
        keywords = load_keywords(self._filters_path)
        h1 = await fetch_hackerone(keywords)
        ywh = await fetch_yeswehack(keywords)
        all_programs = h1 + ywh

        seen = load_seen(self._seen_path)
        new_programs = [p for p in all_programs if _program_key(p) not in seen]
        seen.update(_program_key(p) for p in all_programs)
        save_seen(seen, path=self._seen_path)

        report = build_report(new_programs, total_scanned=len(all_programs))
        return await emit_alert_or_silence(
            report, embed_builder=build_bounty_embed, agent_name=self.name
        )


__all__ = [
    "DEFAULT_FILTERS_PATH",
    "DEFAULT_KEYWORDS",
    "DEFAULT_SEEN_PATH",
    "HACKERONE_PROGRAMS_URL",
    "SERVICE_NAME",
    "YESWEHACK_PROGRAMS_URL",
    "BountyProgram",
    "BountyRadar",
    "BountyReport",
    "build_bounty_embed",
    "build_report",
    "fetch_hackerone",
    "fetch_yeswehack",
    "load_keywords",
    "load_seen",
    "save_seen",
]
