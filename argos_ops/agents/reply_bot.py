"""ReplyBot — drafte des réponses aux mentions sociales (humain-validé).

Pipeline shadow strict (Sprint 3+ / Comm) :

1. Lit ``data/social/mentions.yaml`` (alimenté par export manuel ou
   futur fetch LinkedIn / Mastodon mentions API)
2. Filtre les mentions ``status: pending`` (pas encore traitées)
3. Drafte une réponse courte courtoise dans
   ``data/social/reply_drafts/<mention_id>.md`` avec frontmatter
   (status: drafted, platform, mention_url, author, original_text, draft_reply)
4. Pas de publish — humain-in-the-loop via ContentBot ou copy/paste manuel

Cap journalier : DAILY_MAX (10) pour éviter de drafter en boucle si
le YAML grossit.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml
from loguru import logger

from argos_ops.agents.base import BaseAgent, RunResult
from argos_ops.config import REPO_ROOT, get_settings
from argos_ops.notifications.discord import GREEN, YELLOW, Embed, EmbedField, send_embed

MENTIONS_PATH = REPO_ROOT / "data" / "social" / "mentions.yaml"
DRAFTS_DIR = REPO_ROOT / "data" / "social" / "reply_drafts"
DAILY_MAX = 10


@dataclass
class Mention:
    id: str
    platform: str  # 'linkedin' | 'mastodon'
    author: str
    mention_url: str
    original_text: str
    sentiment: str = "neutral"  # 'positive' | 'neutral' | 'negative' (manuel)
    status: str = "pending"


@dataclass
class ReplyStats:
    mentions_read: int = 0
    pending: int = 0
    drafted: int = 0
    skipped_existing: int = 0
    by_platform: dict[str, int] = field(default_factory=dict)

    def summary(self) -> str:
        return (
            f"read={self.mentions_read} pending={self.pending} "
            f"drafted={self.drafted} existing={self.skipped_existing}"
        )


def load_mentions(path: Path | None = None) -> list[Mention]:
    path = path or MENTIONS_PATH
    if not path.exists():
        return []
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    out: list[Mention] = []
    for entry in raw.get("mentions", []):
        if not isinstance(entry, dict):
            continue
        try:
            out.append(
                Mention(
                    id=str(entry["id"]),
                    platform=str(entry.get("platform", "linkedin")),
                    author=str(entry.get("author", "anonymous")),
                    mention_url=str(entry.get("mention_url", "")),
                    original_text=str(entry.get("original_text", "")),
                    sentiment=str(entry.get("sentiment", "neutral")),
                    status=str(entry.get("status", "pending")),
                )
            )
        except KeyError:
            continue
    return out


def draft_reply(mention: Mention) -> str:
    """Drafte une réponse minimale courtoise, dépendant du sentiment."""
    if mention.sentiment == "positive":
        reply = (
            f"Merci {mention.author} ! Si tu veux pousser le sujet, "
            f"DM ouverts ou contact@omnividens.fr."
        )
    elif mention.sentiment == "negative":
        reply = (
            f"Merci pour le feedback {mention.author}. On préfère traiter ce "
            f"point en direct — peux-tu me ping en DM ou contact@omnividens.fr ?"
        )
    else:
        reply = (
            f"Hello {mention.author}, merci pour la mention. On regarde et "
            f"on revient vers toi rapidement si pertinent."
        )
    return (
        f"---\nstatus: drafted\nid: {mention.id}\nplatform: {mention.platform}\n"
        f"author: {mention.author}\nmention_url: {mention.mention_url}\n"
        f"sentiment: {mention.sentiment}\n---\n\n"
        f"## Mention originale\n\n> {mention.original_text}\n\n"
        f"## Réponse draftée\n\n{reply}\n"
    )


def build_reply_embed(stats: ReplyStats) -> Embed:
    color = GREEN if stats.drafted > 0 or stats.pending == 0 else YELLOW
    fields = [
        EmbedField(name="Mentions lues", value=str(stats.mentions_read), inline=True),
        EmbedField(name="En attente", value=str(stats.pending), inline=True),
        EmbedField(name="Draftées", value=str(stats.drafted), inline=True),
        EmbedField(name="Déjà draftées", value=str(stats.skipped_existing), inline=True),
    ]
    if stats.by_platform:
        breakdown = ", ".join(f"{p}={n}" for p, n in stats.by_platform.items())
        fields.append(EmbedField(name="Par plateforme", value=breakdown, inline=False))
    return Embed(
        title=f"Argos — ReplyBot ({stats.drafted} réponses draftées)",
        color=color,
        fields=fields,
        footer="Argos Ops • ReplyBot",
    )


class ReplyBot(BaseAgent):
    """Drafte des réponses aux mentions LinkedIn / Mastodon — humain-validé."""

    name = "ReplyBot"
    command = "/draft-replies"
    breaker_name = "ReplyBot"

    async def run(self) -> RunResult:
        mentions = load_mentions()
        stats = ReplyStats(mentions_read=len(mentions))
        pending = [m for m in mentions if m.status == "pending"]
        stats.pending = len(pending)

        DRAFTS_DIR.mkdir(parents=True, exist_ok=True)
        for mention in pending[:DAILY_MAX]:
            stats.by_platform[mention.platform] = (
                stats.by_platform.get(mention.platform, 0) + 1
            )
            path = DRAFTS_DIR / f"{mention.id}.md"
            if path.exists():
                stats.skipped_existing += 1
                continue
            try:
                path.write_text(draft_reply(mention), encoding="utf-8")
                stats.drafted += 1
            except OSError as exc:
                logger.warning(f"ReplyBot — écriture {mention.id} : {exc}")

        settings = get_settings()
        webhook = settings.discord_webhook_content or settings.discord_webhook_ops_logs
        if webhook is not None and stats.pending > 0:
            try:
                await send_embed(webhook, build_reply_embed(stats))
            except Exception as exc:
                logger.warning(f"ReplyBot — notif Discord : {exc}")

        return RunResult(status="success", output_summary=stats.summary())


__all__ = [
    "DAILY_MAX",
    "DRAFTS_DIR",
    "MENTIONS_PATH",
    "Mention",
    "ReplyBot",
    "ReplyStats",
    "build_reply_embed",
    "draft_reply",
    "load_mentions",
]
