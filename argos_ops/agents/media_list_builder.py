"""MediaListBuilder — maintient la DB des journalistes / médias cyber.

Mode shadow strict : pas de scraping LinkedIn / annuaires. Le bot
maintient ``data/comm/media_list.yaml`` qui sert de répertoire founder.
À chaque run, il :

1. Lit le YAML
2. Calcule des métriques (par segment : presse spécialisée cyber,
   presse business, podcasts, blogs influents)
3. Détecte les fiches incomplètes (email manquant, pas de beat assigné)
4. Notifie Discord uniquement si nouvelles fiches ou trous détectés
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from loguru import logger

from argos_ops.agents.base import BaseAgent, RunResult
from argos_ops.config import REPO_ROOT, get_settings
from argos_ops.notifications.discord import GREEN, YELLOW, Embed, EmbedField, send_embed

MEDIA_LIST_PATH = REPO_ROOT / "data" / "comm" / "media_list.yaml"


@dataclass
class MediaContact:
    slug: str
    name: str
    outlet: str
    beat: str = ""  # 'cyber', 'startup', 'tech', 'business'
    email: str = ""
    twitter: str = ""
    last_interaction: str = ""  # ISO date

    @property
    def is_complete(self) -> bool:
        return bool(self.email and self.beat)


@dataclass
class ListReport:
    total: int
    by_beat: Counter[str] = field(default_factory=Counter)
    incomplete: list[str] = field(default_factory=list)

    @property
    def has_signal(self) -> bool:
        return self.total > 0 and (len(self.incomplete) > 0 or self.total <= 10)

    def summary(self) -> str:
        breakdown = ",".join(f"{k}={v}" for k, v in self.by_beat.most_common())
        return f"total={self.total} incomplete={len(self.incomplete)} ({breakdown})"


def load_media_list(path: Path | None = None) -> list[MediaContact]:
    path = path or MEDIA_LIST_PATH
    if not path.exists():
        return []
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    out: list[MediaContact] = []
    for entry in raw.get("contacts", []):
        if not isinstance(entry, dict):
            continue
        try:
            out.append(
                MediaContact(
                    slug=str(entry["slug"]),
                    name=str(entry["name"]),
                    outlet=str(entry.get("outlet", "")),
                    beat=str(entry.get("beat", "")),
                    email=str(entry.get("email", "")),
                    twitter=str(entry.get("twitter", "")),
                    last_interaction=str(entry.get("last_interaction", "")),
                )
            )
        except KeyError:
            continue
    return out


def build_report(contacts: list[MediaContact]) -> ListReport:
    report = ListReport(total=len(contacts))
    for c in contacts:
        if c.beat:
            report.by_beat[c.beat] += 1
        if not c.is_complete:
            report.incomplete.append(c.slug)
    return report


def build_list_embed(report: ListReport) -> Embed:
    color = YELLOW if report.incomplete or report.total < 10 else GREEN
    fields = [
        EmbedField(name="Total contacts", value=str(report.total), inline=True),
        EmbedField(name="Incomplets", value=str(len(report.incomplete)), inline=True),
    ]
    for beat, n in report.by_beat.most_common():
        fields.append(EmbedField(name=beat, value=str(n), inline=True))
    if report.incomplete:
        fields.append(
            EmbedField(
                name="À compléter",
                value="\n".join(f"• {s}" for s in report.incomplete[:5]),
                inline=False,
            )
        )
    return Embed(
        title="Argos — MediaListBuilder",
        color=color,
        fields=fields,
        footer="Argos Ops • MediaListBuilder",
    )


class MediaListBuilder(BaseAgent):
    """Audit hebdo de la DB journalistes / médias cyber."""

    name = "MediaListBuilder"
    command = "/run-media-list-build"
    breaker_name = "MediaListBuilder"
    ai_act_risk_class = "limited"

    async def run(self) -> RunResult:
        contacts = load_media_list()
        report = build_report(contacts)

        settings = get_settings()
        webhook = settings.discord_webhook_alerts or settings.discord_webhook_ops_logs
        if webhook is not None and report.has_signal:
            try:
                await send_embed(webhook, build_list_embed(report))
            except Exception as exc:
                logger.warning(f"MediaListBuilder — notif Discord : {exc}")

        return RunResult(status="success", output_summary=report.summary())


__all__ = [
    "MEDIA_LIST_PATH",
    "ListReport",
    "MediaContact",
    "MediaListBuilder",
    "build_list_embed",
    "build_report",
    "load_media_list",
]
