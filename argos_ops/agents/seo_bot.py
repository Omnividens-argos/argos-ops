"""SEOBot — SEO Content Lead (P22.I — health-check passif).

Le drafting des briefs SEO se fait via le slash ``/generate-seo-brief``
(humain-in-the-loop, invoque le skill markdown ``seo-brief-writer``).
L'agent Python ne fait donc qu'un **health-check passif** : il compte
les briefs présents dans ``data/seo/briefs/`` pour exposer un état au
panel Admin et à BotHealthBot.

Pattern identique à :class:`argos_ops.agents.decision_logger.DecisionLogger` :
- ``run()`` retourne un snapshot read-only (nombre de briefs présents,
  dernier brief écrit)
- L'append interactif reste 100 % côté slash command

Cf. plan ``docs/ARGOS_OPS_PLAN.md`` Annexe D § 4 Marketing & Growth.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from argos_ops.agents.base import BaseAgent, RunResult
from argos_ops.config import REPO_ROOT
from argos_ops.exceptions import AgentDataSourceError

DEFAULT_BRIEFS_DIR: Path = REPO_ROOT / "data" / "seo" / "briefs"


class SEOBot(BaseAgent):
    """SEO Content Lead — health-check des briefs SEO présents."""

    name = "SEOBot"
    command = "/generate-seo-brief"
    breaker_name = None
    ai_act_risk_class = "minimal"

    def __init__(self, *, briefs_dir: Path | None = None) -> None:
        self._briefs_dir = briefs_dir or DEFAULT_BRIEFS_DIR

    async def run(self) -> RunResult:
        """Compte les briefs SEO présents, retourne le snapshot.

        Le drafting réel est fait par le slash ``/generate-seo-brief``
        en humain-in-the-loop, pas par cette méthode.
        """
        if not self._briefs_dir.exists():
            return RunResult(
                status="success",
                output_summary="0 briefs (data/seo/briefs/ absent)",
                extras={"briefs_count": 0, "path": str(self._briefs_dir)},
            )
        try:
            briefs = sorted(self._briefs_dir.glob("*.md"))
        except OSError as exc:
            raise AgentDataSourceError(
                f"scan {self._briefs_dir.name}: {exc}"
            ) from exc
        latest = max(briefs, key=lambda p: p.stat().st_mtime).name if briefs else None
        return RunResult(
            status="success",
            output_summary=f"{len(briefs)} briefs présents · latest={latest}",
            extras={
                "briefs_count": len(briefs),
                "latest_brief": latest,
                "checked_at": datetime.now(UTC).isoformat(),
                "path": str(self._briefs_dir),
            },
        )


__all__ = ["DEFAULT_BRIEFS_DIR", "SEOBot"]
