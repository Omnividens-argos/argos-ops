"""FeedbackAggregator — Product Discovery (P22.G Produit Sprint 11).

Agrège les demandes clients (emails, support, Discord) par thème, depuis
un fichier YAML cumulé manuellement par le founder ::

    items:
      - source: "email"            # email | support | discord | call
        customer_id: "acme-sa"
        date: "2026-05-18"
        topic: "Export PDF en français"
        verbatim: "On aimerait avoir l'export rapport disponible en FR."

Le bot cluster par ``topic`` (clé exacte, simple comptage), retourne le
top demande + un digest Markdown ``data/feedback/digest_<YYYY-MM-DD>.md``.
Idempotent : un digest du même jour est écrasé.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

import yaml
from loguru import logger

from argos_ops.agents.base import BaseAgent, IOItem, RunResult
from argos_ops.config import REPO_ROOT, get_settings
from argos_ops.notifications.discord import (
    GREEN,
    YELLOW,
    Embed,
    EmbedField,
    send_embed,
)

DEFAULT_ITEMS_PATH: Path = REPO_ROOT / "data" / "feedback" / "items.yaml"
DEFAULT_DIGEST_DIR: Path = REPO_ROOT / "data" / "feedback"


@dataclass(frozen=True)
class FeedbackTheme:
    """Thème agrégé."""

    topic: str
    count: int
    sources: list[str]  # ex : ["email x 2", "support x 1"]
    customers: list[str]  # customer_ids uniques


@dataclass
class FeedbackReport:
    items_total: int = 0
    themes: list[FeedbackTheme] = field(default_factory=list)

    def summary(self) -> str:
        return f"items={self.items_total} themes={len(self.themes)}"


def _load_items(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    items = raw.get("items", [])
    if not isinstance(items, list):
        raise ValueError(f"feedback/items.yaml malformé : {path}")
    return items


def aggregate(items: list[dict[str, Any]]) -> list[FeedbackTheme]:
    """Agrège les items par ``topic`` (clé exacte)."""
    by_topic: dict[str, list[dict[str, Any]]] = {}
    for item in items:
        topic = (item.get("topic") or "").strip()
        if not topic:
            continue
        by_topic.setdefault(topic, []).append(item)

    themes: list[FeedbackTheme] = []
    for topic, group in by_topic.items():
        source_counter: Counter[str] = Counter()
        customers: list[str] = []
        for entry in group:
            source_counter[entry.get("source", "unknown")] += 1
            cid = entry.get("customer_id")
            if cid and cid not in customers:
                customers.append(cid)
        sources_render = [f"{src} x {n}" for src, n in source_counter.most_common()]
        themes.append(
            FeedbackTheme(
                topic=topic,
                count=len(group),
                sources=sources_render,
                customers=customers,
            )
        )
    themes.sort(key=lambda t: t.count, reverse=True)
    return themes


def render_digest(report: FeedbackReport, *, today: date) -> str:
    parts = [f"# Feedback clients — digest {today.isoformat()}\n"]
    parts.append(
        f"> {report.items_total} item(s) agrégé(s) en {len(report.themes)} thème(s). "
        f"Source unique : `data/feedback/items.yaml`.\n"
    )
    for idx, theme in enumerate(report.themes, start=1):
        parts.append(f"\n## {idx}. {theme.topic} ({theme.count} mentions)\n")
        parts.append(f"- **Sources** : {', '.join(theme.sources)}")
        if theme.customers:
            parts.append(f"- **Clients** : {', '.join(theme.customers)}")
    if not report.themes:
        parts.append("\n_(Aucun thème — `data/feedback/items.yaml` vide.)_\n")
    return "\n".join(parts) + "\n"


def build_feedback_embed(report: FeedbackReport) -> Embed:
    color = YELLOW if report.themes else GREEN
    fields = [
        EmbedField(name="Items", value=str(report.items_total), inline=True),
        EmbedField(name="Thèmes", value=str(len(report.themes)), inline=True),
    ]
    if report.themes:
        top = report.themes[:5]
        lines = [f"• **{t.topic}** ({t.count} mentions)" for t in top]
        fields.append(EmbedField(name="Top demandes", value="\n".join(lines), inline=False))
    return Embed(
        title=f"FeedbackAggregator — {len(report.themes)} thème(s) consolidé(s)",
        description=(
            "Digest dans `data/feedback/digest_<date>.md` — input pour les "
            "prochains arbitrages produit."
            if report.themes
            else "Aucune demande à agréger."
        ),
        color=color,
        fields=fields,
        footer="Argos Ops • FeedbackAggregator",
    )


class FeedbackAggregator(BaseAgent):
    """Agrège les demandes clients par thème → digest Markdown."""

    name = "FeedbackAggregator"
    command = "/run-feedback-digest"
    breaker_name = "FeedbackAggregator"
    ai_act_risk_class = "minimal"

    def __init__(
        self,
        *,
        items_path: Path = DEFAULT_ITEMS_PATH,
        digest_dir: Path = DEFAULT_DIGEST_DIR,
    ) -> None:
        self._items_path = items_path
        self._digest_dir = digest_dir

    async def run(self) -> RunResult:
        settings = get_settings()
        items = _load_items(self._items_path)
        if not items:
            logger.info(f"FeedbackAggregator — aucun item ({self._items_path})")
            return RunResult(status="success", output_summary="silence (no items)")

        themes = aggregate(items)
        report = FeedbackReport(items_total=len(items), themes=themes)

        today = date.today()
        self._digest_dir.mkdir(parents=True, exist_ok=True)
        digest_path = self._digest_dir / f"digest_{today.isoformat()}.md"
        digest_path.write_text(render_digest(report, today=today), encoding="utf-8")

        webhook = settings.discord_webhook_ops_logs or settings.discord_webhook_alerts
        if webhook is not None and themes:
            try:
                await send_embed(webhook, build_feedback_embed(report))
            except Exception as exc:
                logger.warning(f"FeedbackAggregator — notif Discord échouée : {exc}")

        inputs = [
            IOItem(
                label="Demandes clients brutes",
                kind="file",
                detail=f"clusterisées en {len(themes)} thème(s)",
                ref="data/feedback/items.yaml",
                count=len(items),
            )
        ]
        outputs = [
            IOItem(
                label="Digest feedback par thème",
                kind="file",
                detail="; ".join(f"{t.topic} ({t.count})" for t in themes[:3]),
                ref=f"data/feedback/{digest_path.name}",
                count=len(themes),
            )
        ]

        return RunResult(
            status="success",
            output_summary=report.summary(),
            inputs=inputs,
            outputs=outputs,
        )


__all__ = [
    "DEFAULT_DIGEST_DIR",
    "DEFAULT_ITEMS_PATH",
    "FeedbackAggregator",
    "FeedbackReport",
    "FeedbackTheme",
    "aggregate",
    "build_feedback_embed",
    "render_digest",
]
