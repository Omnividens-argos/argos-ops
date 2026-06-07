"""TrendSpotter — repère les sujets cyber chauds pour ContentBot / SEOBot.

Lit ``data/trends/sources.yaml``, garde la fenêtre 14j, trie par score
(récence x poids), et écrit un digest top-5 dans
``data/trends/digest-<date>.md`` consommable par ``/draft-content``
ou ``/generate-seo-brief``.

Mode shadow strict : aucun scraping ici. Le fichier sources.yaml est
maintenu via veille founder ou futur agent dédié.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from loguru import logger

from argos_ops.agents.base import BaseAgent, RunResult
from argos_ops.config import REPO_ROOT, get_settings
from argos_ops.marketing.trends import load_trend_sources, score_trends
from argos_ops.notifications.discord import GREEN, YELLOW, Embed, EmbedField, send_embed

DIGEST_DIR = REPO_ROOT / "data" / "trends"


@dataclass
class TrendDigest:
    top: list[str]
    total_fresh: int
    digest_path: Path | None

    def summary(self) -> str:
        return f"fresh={self.total_fresh} top={len(self.top)}"


def write_digest(top_titles: list[str], *, now: datetime | None = None) -> Path:
    """Écrit le digest top-N dans data/trends/digest-YYYY-MM-DD.md."""
    now = now or datetime.now(UTC)
    DIGEST_DIR.mkdir(parents=True, exist_ok=True)
    path = DIGEST_DIR / f"digest-{now.date().isoformat()}.md"
    lines = [f"# Argos — trends top {len(top_titles)} ({now.date()})", ""]
    for i, title in enumerate(top_titles, start=1):
        lines.append(f"{i}. {title}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def build_trend_embed(digest: TrendDigest) -> Embed:
    color = GREEN if digest.top else YELLOW
    fields = [
        EmbedField(name="Items frais (14j)", value=str(digest.total_fresh), inline=True),
        EmbedField(name="Top retenus", value=str(len(digest.top)), inline=True),
    ]
    if digest.top:
        fields.append(
            EmbedField(
                name="Top sujets",
                value="\n".join(f"• {t}" for t in digest.top[:5]),
                inline=False,
            )
        )
    return Embed(
        title="Argos — TrendSpotter",
        color=color,
        fields=fields,
        footer="Argos Ops • TrendSpotter",
    )


class TrendSpotter(BaseAgent):
    """Repère les sujets cyber chauds dans la fenêtre 14j."""

    name = "TrendSpotter"
    command = "/run-trend-spot"
    breaker_name = "TrendSpotter"
    ai_act_risk_class = "minimal"

    async def run(self) -> RunResult:
        items = load_trend_sources()
        fresh = score_trends(items, lookback_days=14)
        top_titles = [i.title for i in fresh[:5]]

        path: Path | None = None
        if top_titles:
            path = write_digest(top_titles)

        digest = TrendDigest(top=top_titles, total_fresh=len(fresh), digest_path=path)

        settings = get_settings()
        webhook = settings.discord_webhook_content or settings.discord_webhook_ops_logs
        if webhook is not None and top_titles:
            try:
                await send_embed(webhook, build_trend_embed(digest))
            except Exception as exc:
                logger.warning(f"TrendSpotter — notif Discord a échoué : {exc}")

        # « Se souvenir » (fleet memory) : chaque sujet chaud devient un fait
        # conservé, lisible par ContentBot / EditorialBot / les writers / SEOBot
        # (cf. graphe d'accès data/fleet_memory/MEMORY.md). TTL 21j = un sujet
        # chaud se périme. Idempotent : un sujet re-détecté ne se duplique pas.
        fleet_facts = [
            {
                "body": f"Sujet cyber chaud (fenêtre 14j) : {title}",
                "kind": "trend",
                "confidence": "high" if rank < 3 else "medium",
                "ttl_days": 21,
                "tags": ["trend", "cyber"],
            }
            for rank, title in enumerate(top_titles)
        ]
        return RunResult(
            status="success",
            output_summary=digest.summary(),
            extras={"fleet_facts": fleet_facts},
        )


__all__ = ["TrendDigest", "TrendSpotter", "build_trend_embed", "write_digest"]
