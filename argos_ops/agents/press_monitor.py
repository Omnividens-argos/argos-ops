"""PressMonitor — détecte les mentions Argos / Omnividens / SecHunter sur le web.

Mode shadow strict (Sprint 5 Comm) : pas de scraper généraliste ici.
Le bot lit ``data/comm/press_mentions.yaml`` (alimenté manuellement
depuis Google Alerts ou veille founder) et :

1. Filtre les nouvelles entrées (``status: new``)
2. Notifie Discord avec un récap (auteur, source, ton estimé)
3. Marque les entrées notifiées status: ack en réécrivant le YAML

Aucun appel web — la collecte reste manuelle / Google Alerts free.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml
from loguru import logger

from argos_ops.agents.base import BaseAgent, IOItem, RunResult
from argos_ops.config import REPO_ROOT, get_settings
from argos_ops.notifications.discord import (
    GREEN,
    ORANGE,
    YELLOW,
    Embed,
    EmbedField,
    send_embed,
)

MENTIONS_PATH = REPO_ROOT / "data" / "comm" / "press_mentions.yaml"


@dataclass
class PressMention:
    id: str
    source: str
    url: str
    title: str
    sentiment: str = "neutral"
    status: str = "new"


@dataclass
class MonitorReport:
    total: int
    new_mentions: list[PressMention]
    negatives: int

    @property
    def should_alert(self) -> bool:
        return len(self.new_mentions) > 0

    @property
    def color(self) -> int:
        if self.negatives > 0:
            return ORANGE
        if self.new_mentions:
            return YELLOW
        return GREEN

    def summary(self) -> str:
        return f"total={self.total} new={len(self.new_mentions)} negatives={self.negatives}"


def load_mentions(path: Path | None = None) -> list[PressMention]:
    path = path or MENTIONS_PATH
    if not path.exists():
        return []
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    out: list[PressMention] = []
    for entry in raw.get("mentions", []):
        if not isinstance(entry, dict):
            continue
        try:
            out.append(
                PressMention(
                    id=str(entry["id"]),
                    source=str(entry.get("source", "")),
                    url=str(entry.get("url", "")),
                    title=str(entry.get("title", "")),
                    sentiment=str(entry.get("sentiment", "neutral")),
                    status=str(entry.get("status", "new")),
                )
            )
        except KeyError:
            continue
    return out


def mark_ack(mentions: list[PressMention], ack_ids: set[str], path: Path | None = None) -> None:
    """Réécrit le YAML en passant ack_ids à status: ack."""
    path = path or MENTIONS_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    out: list[dict[str, object]] = []
    for m in mentions:
        status = "ack" if m.id in ack_ids else m.status
        out.append(
            {
                "id": m.id,
                "source": m.source,
                "url": m.url,
                "title": m.title,
                "sentiment": m.sentiment,
                "status": status,
            }
        )
    path.write_text(yaml.safe_dump({"mentions": out}, allow_unicode=True), encoding="utf-8")


def build_monitor_embed(report: MonitorReport) -> Embed:
    fields = [
        EmbedField(name="Total mentions", value=str(report.total), inline=True),
        EmbedField(name="Nouvelles", value=str(len(report.new_mentions)), inline=True),
        EmbedField(name="Négatives", value=str(report.negatives), inline=True),
    ]
    if report.new_mentions:
        preview = [
            f"• {m.source} — {m.title[:60]}" for m in report.new_mentions[:5]
        ]
        fields.append(EmbedField(name="Aperçu", value="\n".join(preview), inline=False))
    return Embed(
        title=f"Argos — PressMonitor ({len(report.new_mentions)} nouvelles)",
        color=report.color,
        fields=fields,
        footer="Argos Ops • PressMonitor",
    )


class PressMonitor(BaseAgent):
    """Détecte les nouvelles mentions presse et notifie le founder."""

    name = "PressMonitor"
    command = "/run-press-monitor"
    breaker_name = "PressMonitor"
    ai_act_risk_class = "minimal"

    async def run(self) -> RunResult:
        mentions = load_mentions()
        new = [m for m in mentions if m.status == "new"]
        negatives = sum(1 for m in new if m.sentiment == "negative")
        report = MonitorReport(total=len(mentions), new_mentions=new, negatives=negatives)

        settings = get_settings()
        webhook = settings.discord_webhook_alerts or settings.discord_webhook_ops_logs
        if webhook is not None and report.should_alert:
            try:
                await send_embed(webhook, build_monitor_embed(report))
            except Exception as exc:
                logger.warning(f"PressMonitor — notif Discord : {exc}")

        if new and mentions:
            mark_ack(mentions, ack_ids={m.id for m in new})

        outputs: list[IOItem] = []
        if report.should_alert and webhook is not None:
            outputs.append(
                IOItem(
                    label="Alerte mentions presse → Discord",
                    kind="discord",
                    detail=f"{report.negatives} négative(s)",
                    count=len(new),
                )
            )
        if new and mentions:
            outputs.append(
                IOItem(
                    label="Mentions marquées ack",
                    kind="file",
                    ref="data/comm/press_mentions.yaml",
                    count=len(new),
                )
            )
        return RunResult(
            status="success",
            output_summary=report.summary(),
            inputs=[
                IOItem(
                    label="Veille mentions presse",
                    kind="file",
                    detail="Google Alerts / veille founder · status=new filtrés",
                    ref="data/comm/press_mentions.yaml",
                    count=report.total,
                )
            ],
            outputs=outputs,
        )


__all__ = [
    "MENTIONS_PATH",
    "MonitorReport",
    "PressMention",
    "PressMonitor",
    "build_monitor_embed",
    "load_mentions",
    "mark_ack",
]
