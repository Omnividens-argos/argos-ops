"""NewsletterBot — drafte la newsletter mensuelle Argos (Sprint 12).

Pipeline local-draft (humain-in-the-loop) :

1. Lit ``data/blog/index.yaml`` (posts publiés depuis le dernier envoi)
2. Lit ``data/trends/digest-*.md`` produits par TrendSpotter (14 derniers
   jours) pour insérer une section « actu cyber »
3. Construit un Markdown structuré dans ``data/newsletters/drafts/
   YYYY-MM.md`` avec frontmatter (status: draft, ready_for_review,
   subject, send_window)
4. Notif Discord avec lien vers le draft pour validation founder
5. **N'envoie rien** — l'envoi via Zimbra reste manuel jusqu'à validation
   wording founder (cohérent D-018)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path

import yaml
from loguru import logger

from argos_ops.agents.base import BaseAgent, RunResult
from argos_ops.config import REPO_ROOT, get_settings
from argos_ops.notifications.discord import GREEN, YELLOW, Embed, EmbedField, send_embed

BLOG_INDEX = REPO_ROOT / "data" / "blog" / "index.yaml"
TRENDS_DIR = REPO_ROOT / "data" / "trends"
NEWSLETTER_DIR = REPO_ROOT / "data" / "newsletters" / "drafts"


@dataclass
class NewsletterDraft:
    month: str  # ex : "2026-05"
    path: Path
    blog_count: int
    trends_count: int

    def summary(self) -> str:
        return f"month={self.month} blog={self.blog_count} trends={self.trends_count}"


def _load_blog_posts() -> list[dict[str, object]]:
    if not BLOG_INDEX.exists():
        return []
    data = yaml.safe_load(BLOG_INDEX.read_text(encoding="utf-8")) or {}
    return [p for p in data.get("posts", []) if isinstance(p, dict)]


def _load_trend_digests() -> list[str]:
    if not TRENDS_DIR.exists():
        return []
    digests: list[str] = []
    for path in sorted(TRENDS_DIR.glob("digest-*.md")):
        try:
            digests.append(path.read_text(encoding="utf-8"))
        except OSError:
            continue
    return digests


def build_newsletter_markdown(
    *,
    month: str,
    blog_posts: list[dict[str, object]],
    trend_digests: list[str],
) -> str:
    """Construit le Markdown de la newsletter du mois."""
    lines: list[str] = [
        "---",
        "status: draft",
        f"month: {month}",
        f"subject: Argos — récap {month}",
        "send_window: D+0 à D+3 (mardi 10h Paris préféré)",
        "---",
        "",
        f"# Newsletter Argos — {month}",
        "",
        "## Au sommaire",
        "",
    ]
    if blog_posts:
        lines.append("### Articles récents")
        for post in blog_posts[:5]:
            title = post.get("title", "Sans titre")
            url = post.get("url", "")
            lines.append(f"- [{title}]({url})")
        lines.append("")
    if trend_digests:
        lines.append("### Actu cyber notable")
        # On prend juste le digest le plus récent pour ne pas saturer
        lines.append(trend_digests[-1].strip())
        lines.append("")
    lines.extend(
        [
            "### Côté Argos",
            "",
            "_À compléter par le fondateur : 2-3 phrases produit, releases du mois, prochaines démos._",
            "",
            "---",
            "",
            "*Vous recevez cet email car vous êtes inscrit·e à la newsletter Argos.*",
            "*Désabonnement : envoyez « stop » à contact@omnividens.fr.*",
            "",
        ]
    )
    return "\n".join(lines)


def write_draft(month: str, content: str) -> Path:
    NEWSLETTER_DIR.mkdir(parents=True, exist_ok=True)
    path = NEWSLETTER_DIR / f"{month}.md"
    path.write_text(content, encoding="utf-8")
    return path


def build_newsletter_embed(draft: NewsletterDraft) -> Embed:
    color = YELLOW if draft.blog_count == 0 and draft.trends_count == 0 else GREEN
    return Embed(
        title=f"Argos — NewsletterBot ({draft.month})",
        color=color,
        fields=[
            EmbedField(name="Articles", value=str(draft.blog_count), inline=True),
            EmbedField(name="Digests cyber", value=str(draft.trends_count), inline=True),
            EmbedField(name="Draft", value=draft.path.name, inline=False),
        ],
        footer="Argos Ops • NewsletterBot",
    )


class NewsletterBot(BaseAgent):
    """Drafte la newsletter mensuelle — humain-in-the-loop pour l'envoi."""

    name = "NewsletterBot"
    command = "/draft-newsletter"
    breaker_name = "NewsletterBot"

    def _month_str(self, now: datetime | None = None) -> str:
        now = now or datetime.now(UTC)
        return f"{now.year:04d}-{now.month:02d}"

    async def run(self) -> RunResult:
        month = self._month_str()
        blog = _load_blog_posts()
        digests = _load_trend_digests()
        md = build_newsletter_markdown(
            month=month, blog_posts=blog, trend_digests=digests
        )
        path = write_draft(month, md)

        draft = NewsletterDraft(
            month=month, path=path, blog_count=len(blog), trends_count=len(digests)
        )
        logger.info(f"NewsletterBot — draft écrit {path}")

        settings = get_settings()
        webhook = settings.discord_webhook_content or settings.discord_webhook_ops_logs
        if webhook is not None:
            try:
                await send_embed(webhook, build_newsletter_embed(draft))
            except Exception as exc:
                logger.warning(f"NewsletterBot — notif Discord a échoué : {exc}")

        return RunResult(status="success", output_summary=draft.summary())


__all__ = [
    "BLOG_INDEX",
    "NEWSLETTER_DIR",
    "TRENDS_DIR",
    "NewsletterBot",
    "NewsletterDraft",
    "build_newsletter_embed",
    "build_newsletter_markdown",
    "write_draft",
]


def _today() -> date:
    return datetime.now(UTC).date()
