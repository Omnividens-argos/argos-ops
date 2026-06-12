"""CompetitorWatcher — Competitive Intel (P22.D Veille Sprint 6).

Scrape hebdo les pages publiques ``/pricing`` et ``/features`` de
quelques concurrents (Acunetix, Detectify, Burp Pro, Intruder, Pentera)
et compare le contenu texte vs snapshot précédent. Toute modification
détectée = embed Discord (jaune) pour décision humaine
(« positionnement à mettre à jour »).

Politique anti-spam :
- **Silence** Discord si aucune page n'a bougé (hash sha256 stable
  ou cache hit)
- **Embed jaune** si ≥1 page a changé (modification de pricing ou
  features est intéressant mais jamais critique)

Garde-fous anti-hammering :
- Cache disque 24 h via :mod:`argos_ops.agents._fetcher_base`. Un scrape
  hebdomadaire en cron ne tire donc en réalité du réseau qu'au plus une
  fois sur 7 j par URL.
- User-Agent explicite ``Argos-Ops/competitor-watcher (+...)`` — les
  concurrents peuvent nous bloquer s'ils le souhaitent, on ne se cache pas.
- Pas de parsing HTML profond — on hash juste le texte visible. Aucune
  exfiltration de structure ou de patterns business.

Le catalogue des cibles vit dans
``data/competitors/targets.yaml`` (gitignored sauf modèle).

Cf. plan ``docs/ARGOS_OPS_PLAN.md`` Annexe D § 8 Veille, Sprint 6.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import yaml
from loguru import logger

from argos_ops.agents._fetcher_base import fetch
from argos_ops.agents._watcher_base import color_title, emit_alert_or_silence
from argos_ops.agents.base import BaseAgent, IOItem, RunResult
from argos_ops.config import REPO_ROOT
from argos_ops.fleet_memory import FactDraft
from argos_ops.notifications.discord import GREEN, YELLOW, Embed, EmbedField

DEFAULT_TARGETS_PATH: Path = REPO_ROOT / "data" / "competitors" / "targets.yaml"
DEFAULT_SNAPSHOT_DIR: Path = REPO_ROOT / "data" / "competitors" / "snapshots"
SERVICE_NAME = "competitor-watcher"


@dataclass(frozen=True)
class CompetitorTarget:
    """Une page concurrent à scraper — déclarée dans le YAML."""

    name: str
    section: str  # "pricing" | "features" | autre
    url: str


@dataclass(frozen=True)
class CompetitorChange:
    """Résultat de la comparaison sur une page."""

    target: CompetitorTarget
    previous_hash: str | None
    current_hash: str
    changed: bool


@dataclass(frozen=True)
class CompetitorReport:
    """Résultat agrégé du run CompetitorWatcher."""

    changes: list[CompetitorChange]
    should_alert: bool
    alert_color: int
    summary: str


# =============================================================================
# Config — YAML
# =============================================================================
def load_targets(path: Path = DEFAULT_TARGETS_PATH) -> list[CompetitorTarget]:
    """Lit le YAML ``targets.yaml``. Fichier absent → liste vide."""
    if not path.exists():
        return []
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    entries = raw.get("targets", [])
    out: list[CompetitorTarget] = []
    for entry in entries:
        name = entry.get("name")
        url = entry.get("url")
        section = entry.get("section", "page")
        if not name or not url:
            raise ValueError(f"Target mal formé (manque name ou url): {entry!r}")
        out.append(CompetitorTarget(name=name, section=section, url=url))
    return out


# =============================================================================
# Normalisation HTML → texte hashable
# =============================================================================
_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")
_SCRIPT_STYLE_RE = re.compile(r"<(script|style|noscript)[^>]*>.*?</\1>", re.DOTALL | re.IGNORECASE)


def normalize_html(html: str) -> str:
    """Extrait le texte visible et écrase le whitespace.

    Suffit pour détecter qu'un prix a bougé ou qu'une feature a été
    ajoutée. Pas de parsing structuré (lxml/bs4) — sur 5-10 pages, le
    coût d'un parser DOM ne se justifie pas et augmente la surface de
    bugs (CDATA, encodings exotiques, ...).
    """
    stripped_scripts = _SCRIPT_STYLE_RE.sub(" ", html)
    no_tags = _TAG_RE.sub(" ", stripped_scripts)
    return _WS_RE.sub(" ", no_tags).strip()


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# =============================================================================
# Snapshot I/O
# =============================================================================
def _snapshot_path(target: CompetitorTarget, base_dir: Path) -> Path:
    safe_name = re.sub(r"[^a-zA-Z0-9_-]+", "_", f"{target.name}_{target.section}")
    return base_dir / f"{safe_name}.json"


def load_previous_hash(target: CompetitorTarget, base_dir: Path) -> str | None:
    path = _snapshot_path(target, base_dir)
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, ValueError) as exc:
        logger.warning(f"CompetitorWatcher snapshot corrompu ({path.name}): {exc}")
        return None
    value = payload.get("hash") if isinstance(payload, dict) else None
    return str(value) if isinstance(value, str) else None


def save_snapshot_hash(target: CompetitorTarget, *, hash_: str, base_dir: Path) -> None:
    base_dir.mkdir(parents=True, exist_ok=True)
    path = _snapshot_path(target, base_dir)
    path.write_text(
        json.dumps(
            {
                "name": target.name,
                "section": target.section,
                "url": target.url,
                "hash": hash_,
                "fetched_at": datetime.now(UTC).isoformat(),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


# =============================================================================
# Scrape + diff
# =============================================================================
async def compare_target(target: CompetitorTarget, *, snapshot_dir: Path) -> CompetitorChange:
    """Fetch (avec cache 24h) + hash + diff."""
    response = await fetch(target.url, service=SERVICE_NAME)
    current = content_hash(normalize_html(response.body))
    previous = load_previous_hash(target, snapshot_dir)
    changed = previous is not None and previous != current
    return CompetitorChange(
        target=target,
        previous_hash=previous,
        current_hash=current,
        changed=changed,
    )


# =============================================================================
# Report
# =============================================================================
def build_report(changes: list[CompetitorChange]) -> CompetitorReport:
    changed_count = sum(1 for c in changes if c.changed)
    if changed_count:
        alert_color = YELLOW
        summary = f"{changed_count}/{len(changes)} pages concurrent ont bougé"
        should_alert = True
    else:
        alert_color = GREEN
        summary = f"{len(changes)} pages concurrent — stable"
        should_alert = False
    return CompetitorReport(
        changes=changes,
        should_alert=should_alert,
        alert_color=alert_color,
        summary=summary,
    )


# =============================================================================
# Mémoire de flotte
# =============================================================================
_COMPETITOR_FACT_TTL_DAYS = 60
_MAX_COMPETITOR_FACTS_PER_RUN = 5


def build_competitor_facts(changes: list[CompetitorChange]) -> list[FactDraft]:
    """Faits « competitor » pour chaque page concurrent qui a bougé.

    Consommés par ContentBot / EditorialBot / SEOBot / NewsletterBot via le
    graphe d'accès (un changement de pricing concurrent = angle de contenu).
    TTL 60 j : une veille périmée ne doit pas inspirer un post.
    """
    facts: list[FactDraft] = []
    for change in [c for c in changes if c.changed][:_MAX_COMPETITOR_FACTS_PER_RUN]:
        t = change.target
        facts.append(
            FactDraft(
                body=f"Concurrent {t.name} a modifié sa page {t.section} — {t.url}",
                kind="competitor",
                confidence="high",
                tags=["veille", t.section],
                ttl_days=_COMPETITOR_FACT_TTL_DAYS,
            )
        )
    return facts


def build_competitor_embed(report: CompetitorReport, *, now: datetime | None = None) -> Embed:
    now = now or datetime.now(UTC)
    fields = [
        EmbedField(
            name=f"[DIFF] {change.target.name} / {change.target.section}",
            value=f"{change.target.url}",
            inline=False,
        )
        for change in report.changes
        if change.changed
    ]
    title_status = color_title(report.alert_color, green=GREEN, yellow=YELLOW, red=YELLOW)
    return Embed(
        title=f"CompetitorWatcher — {title_status}",
        description=report.summary,
        color=report.alert_color,
        fields=fields,
        footer="Argos Ops • CompetitorWatcher",
        timestamp=now.isoformat(),
    )


class CompetitorWatcher(BaseAgent):
    """Competitive Intel — scrape hebdo pages concurrents et alerte sur diff."""

    name = "CompetitorWatcher"
    command = "/run-competitor-watch"
    breaker_name = None
    ai_act_risk_class = "minimal"

    def __init__(
        self,
        *,
        targets_path: Path = DEFAULT_TARGETS_PATH,
        snapshot_dir: Path = DEFAULT_SNAPSHOT_DIR,
    ) -> None:
        self._targets_path = targets_path
        self._snapshot_dir = snapshot_dir

    async def run(self) -> RunResult:
        targets = load_targets(self._targets_path)
        if not targets:
            logger.info(f"CompetitorWatcher — aucune cible déclarée ({self._targets_path})")
            return RunResult(
                status="success",
                output_summary="silence (aucune cible)",
                extras={"alerted": False, "summary": "0 targets"},
            )

        changes: list[CompetitorChange] = []
        for target in targets:
            try:
                change = await compare_target(target, snapshot_dir=self._snapshot_dir)
            except Exception as exc:
                logger.warning(
                    f"CompetitorWatcher — fetch {target.name} échoué: {type(exc).__name__}: {exc}"
                )
                continue
            changes.append(change)
            if change.changed or change.previous_hash is None:
                # On persiste à chaque fetch réussi : premier run = baseline,
                # diff = on bascule sur le nouveau hash sans alerter à
                # nouveau au prochain tour (politique « changement vu »).
                save_snapshot_hash(target, hash_=change.current_hash, base_dir=self._snapshot_dir)

        report = build_report(changes)
        changed = [c for c in changes if c.changed]
        inputs = [
            IOItem(
                label="Pages concurrent surveillées",
                kind="file",
                detail=str(self._targets_path),
                ref=str(self._targets_path),
                count=len(targets),
            ),
            IOItem(
                label="Snapshots précédents",
                kind="file",
                detail=str(self._snapshot_dir),
                ref=str(self._snapshot_dir),
            ),
        ]
        outputs = [
            IOItem(
                label="Pages ayant changé",
                kind="http",
                detail=", ".join(f"{c.target.name}/{c.target.section}" for c in changed) or None,
                count=len(changed),
            )
        ]
        result = await emit_alert_or_silence(
            report,
            embed_builder=build_competitor_embed,
            agent_name=self.name,
            inputs=inputs,
            outputs=outputs,
        )
        # Mémoire de flotte : un diff concurrent = signal pour le contenu.
        facts = build_competitor_facts(changes)
        if facts:
            result.extras["fleet_facts"] = facts
        return result


__all__ = [
    "DEFAULT_SNAPSHOT_DIR",
    "DEFAULT_TARGETS_PATH",
    "SERVICE_NAME",
    "CompetitorChange",
    "CompetitorReport",
    "CompetitorTarget",
    "CompetitorWatcher",
    "build_competitor_embed",
    "build_competitor_facts",
    "build_report",
    "compare_target",
    "content_hash",
    "load_previous_hash",
    "load_targets",
    "normalize_html",
    "save_snapshot_hash",
]
