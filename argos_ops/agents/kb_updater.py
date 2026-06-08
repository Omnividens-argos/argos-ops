"""KBUpdater — Knowledge Manager (P22.G CS Sprint 7).

Détecte les **gaps KB** depuis les tickets support résolus :
- regroupe les tickets par thème (mots-clés sujet)
- pour chaque thème vu ≥ ``MIN_OCCURRENCES`` fois sans article KB déjà
  publié → scaffold un draft d'article dans
  ``data/knowledge_base/drafts/<slug>.md``

Le draft contient le sujet, la liste des tickets sources et un canevas
d'article (intro, symptôme, cause, fix). Le founder peaufine puis lance
``/draft-kb-update`` qui invoque ``kb-rag`` (P6) + ``claude-judge`` pour
auditer avant publication dans la KB officielle.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from loguru import logger

from argos_ops.agents.base import BaseAgent, IOItem, RunResult
from argos_ops.config import REPO_ROOT, get_settings
from argos_ops.cs.loader import load_tickets
from argos_ops.cs.models import SupportTicket
from argos_ops.notifications.discord import (
    GREEN,
    YELLOW,
    Embed,
    EmbedField,
    send_embed,
)

DEFAULT_TICKETS_PATH: Path = REPO_ROOT / "data" / "support" / "tickets.yaml"
DEFAULT_KB_DIR: Path = REPO_ROOT / "data" / "knowledge_base"
DEFAULT_DRAFTS_DIR: Path = REPO_ROOT / "data" / "knowledge_base" / "drafts"

# Seuil bas — on préfère trop de drafts à pas assez, le founder filtre
MIN_OCCURRENCES = 2

# Stop-words FR/EN — vire les mots vides qui faussent le clustering
_STOP_WORDS = frozenset(
    {
        "le", "la", "les", "un", "une", "des", "de", "du", "et", "ou", "à", "au",
        "aux", "en", "dans", "pour", "par", "avec", "sans", "sur", "sous", "vers",
        "the", "a", "an", "of", "in", "on", "for", "with", "to", "from", "by",
        "is", "are", "was", "were", "be", "been", "being",
        "ne", "pas", "ni", "que", "qui", "quoi", "où", "comment", "pourquoi",
        "ça", "ce", "cet", "cette", "ces", "il", "elle", "ils", "elles",
        "je", "tu", "nous", "vous", "mon", "ton", "son", "mes", "tes", "ses",
        "argos", "scan", "scans",  # trop génériques sur notre produit
    }
)
_WORD_RE = re.compile(r"[a-zà-öø-ÿ0-9]{4,}", re.IGNORECASE)


@dataclass(frozen=True)
class KBGap:
    """Un thème détecté comme gap KB."""

    theme: str
    occurrences: int
    sample_tickets: list[str]  # ticket_ids


@dataclass
class KBUpdaterStats:
    tickets_scanned: int = 0
    themes_detected: int = 0
    drafts_created: int = 0
    drafts_skipped: int = 0
    gaps: list[KBGap] = field(default_factory=list)

    def summary(self) -> str:
        return (
            f"tickets={self.tickets_scanned} themes={self.themes_detected} "
            f"drafted={self.drafts_created} skipped={self.drafts_skipped}"
        )


def _tokens(subject: str) -> set[str]:
    return {tok.lower() for tok in _WORD_RE.findall(subject) if tok.lower() not in _STOP_WORDS}


def detect_gaps(
    tickets: list[SupportTicket],
    *,
    min_occurrences: int = MIN_OCCURRENCES,
) -> list[KBGap]:
    """Cluster les tickets par mot-clé dominant du sujet → liste de gaps."""
    counter: Counter[str] = Counter()
    by_theme: dict[str, list[str]] = {}
    for ticket in tickets:
        for token in _tokens(ticket.subject):
            counter[token] += 1
            by_theme.setdefault(token, []).append(ticket.ticket_id)

    gaps: list[KBGap] = []
    for theme, count in counter.most_common():
        if count < min_occurrences:
            break
        gaps.append(KBGap(theme=theme, occurrences=count, sample_tickets=by_theme[theme][:5]))
    return gaps


def _existing_articles(kb_dir: Path) -> set[str]:
    """Renvoie l'ensemble des slugs déjà présents dans la KB officielle."""
    if not kb_dir.exists():
        return set()
    return {p.stem for p in kb_dir.glob("*.md") if p.is_file()}


def _draft_kb_article(gap: KBGap, drafts_dir: Path) -> Path:
    drafts_dir.mkdir(parents=True, exist_ok=True)
    slug = re.sub(r"[^a-z0-9-]+", "-", gap.theme.lower()).strip("-") or "topic"
    draft_path = drafts_dir / f"{slug}.md"
    front = {
        "theme": gap.theme,
        "occurrences": gap.occurrences,
        "sample_tickets": gap.sample_tickets,
        "status": "draft-skeleton",
    }
    body = (
        f"# {gap.theme.capitalize()} — article KB Argos\n\n"
        f"> Détecté par KBUpdater à partir de {gap.occurrences} tickets clients "
        f"sur ce thème. Tickets sources : {', '.join(gap.sample_tickets)}.\n\n"
        f"## Symptôme\n\nÀ compléter : décrire ce que voit le client (message d'erreur, "
        f"comportement inattendu, blocage UI).\n\n"
        f"## Cause\n\nÀ compléter : pourquoi ça arrive (config, edge case, limite plan).\n\n"
        f"## Fix\n\nÀ compléter : étapes 1-2-3 pour corriger (avec captures si utile).\n\n"
        f"## Prévention\n\nÀ compléter : comment éviter que ça se reproduise.\n\n"
        f"---\n\n"
        f"Workflow : lance `/draft-kb-update {slug}` → invoque `kb-rag` pour vérifier "
        f"qu'aucun article existant ne couvre déjà → invoque `claude-judge` pour audit "
        f"factual/tone → si OK, déplacer dans `data/knowledge_base/{slug}.md`.\n"
    )
    draft_path.write_text(
        f"---\n{yaml.safe_dump(front, allow_unicode=True, sort_keys=False)}---\n\n{body}",
        encoding="utf-8",
    )
    return draft_path


def build_kb_embed(stats: KBUpdaterStats) -> Embed:
    color = YELLOW if stats.drafts_created > 0 else GREEN
    fields = [
        EmbedField(name="Tickets scannés", value=str(stats.tickets_scanned), inline=True),
        EmbedField(name="Thèmes détectés", value=str(stats.themes_detected), inline=True),
        EmbedField(name="Drafts créés", value=str(stats.drafts_created), inline=True),
    ]
    if stats.gaps:
        top = stats.gaps[:5]
        lines = [f"• **{g.theme}** ({g.occurrences} tickets)" for g in top]
        fields.append(EmbedField(name="Top gaps", value="\n".join(lines), inline=False))
    return Embed(
        title=f"KBUpdater — {stats.drafts_created} draft(s) article KB",
        description=(
            "Lance `/draft-kb-update <slug>` pour peaufiner via `kb-rag` + `claude-judge`."
            if stats.drafts_created > 0
            else "Aucun gap KB détecté."
        ),
        color=color,
        fields=fields,
        footer="Argos Ops • KBUpdater",
    )


class KBUpdater(BaseAgent):
    """Détecte gaps KB depuis tickets répétés → drafts d'articles."""

    name = "KBUpdater"
    command = "/draft-kb-update"
    breaker_name = "KBUpdater"
    ai_act_risk_class = "limited"

    def __init__(
        self,
        *,
        tickets_path: Path = DEFAULT_TICKETS_PATH,
        kb_dir: Path = DEFAULT_KB_DIR,
        drafts_dir: Path = DEFAULT_DRAFTS_DIR,
        min_occurrences: int = MIN_OCCURRENCES,
    ) -> None:
        self._tickets_path = tickets_path
        self._kb_dir = kb_dir
        self._drafts_dir = drafts_dir
        self._min_occurrences = min_occurrences

    async def run(self) -> RunResult:
        settings = get_settings()
        tickets = load_tickets(self._tickets_path)
        if not tickets:
            logger.info(f"KBUpdater — aucun ticket ({self._tickets_path})")
            return RunResult(status="success", output_summary="silence (no tickets)")

        existing = _existing_articles(self._kb_dir)
        gaps = detect_gaps(tickets, min_occurrences=self._min_occurrences)
        stats = KBUpdaterStats(tickets_scanned=len(tickets), themes_detected=len(gaps), gaps=gaps)

        for gap in gaps:
            slug = re.sub(r"[^a-z0-9-]+", "-", gap.theme.lower()).strip("-") or "topic"
            if slug in existing or (self._drafts_dir / f"{slug}.md").exists():
                stats.drafts_skipped += 1
                continue
            try:
                _draft_kb_article(gap, self._drafts_dir)
                stats.drafts_created += 1
            except Exception as exc:
                logger.exception(f"KBUpdater — draft {gap.theme} échec : {exc}")

        webhook = settings.discord_webhook_ops_logs or settings.discord_webhook_alerts
        if webhook is not None and stats.drafts_created > 0:
            try:
                await send_embed(webhook, build_kb_embed(stats))
            except Exception as exc:
                logger.warning(f"KBUpdater — notif Discord échouée : {exc}")

        def _rel(p: Path) -> str:
            try:
                return p.relative_to(REPO_ROOT).as_posix()
            except ValueError:
                return str(p)

        inputs = [
            IOItem(
                label="Tickets support résolus",
                kind="file",
                detail="clustering par mot-clé sujet",
                ref=_rel(self._tickets_path),
                count=stats.tickets_scanned,
            )
        ]
        outputs: list[IOItem] = [
            IOItem(
                label="Gaps KB détectés",
                kind="other",
                detail="thèmes vus ≥ seuil sans article existant",
                count=stats.themes_detected,
            )
        ]
        if stats.drafts_created > 0:
            outputs.append(
                IOItem(
                    label="Drafts d'articles KB",
                    kind="draft",
                    detail=f"{stats.drafts_skipped} déjà existant(s) ignoré(s)",
                    ref=_rel(self._drafts_dir),
                    count=stats.drafts_created,
                )
            )

        return RunResult(
            status="success",
            output_summary=stats.summary(),
            inputs=inputs,
            outputs=outputs,
        )


__all__ = [
    "DEFAULT_DRAFTS_DIR",
    "DEFAULT_KB_DIR",
    "DEFAULT_TICKETS_PATH",
    "KBGap",
    "KBUpdater",
    "KBUpdaterStats",
    "build_kb_embed",
    "detect_gaps",
]
