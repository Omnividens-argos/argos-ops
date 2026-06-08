"""StrategyBot — VP Stratégie (P22.E Direction Sprint 9).

Génère un digest hebdomadaire markdown :

- Volume d'exécutions agents (7j)
- Taux de succès / erreur par agent
- Évolution semaine vs semaine
- Top alertes Discord pushées
- Recommandations stratégiques courtes (« concentre-toi sur X »)

Écrit le digest dans ``data/strategy/digest-YYYY-WW.md`` puis push un
résumé Embed Discord sur ``DISCORD_WEBHOOK_OPS_LOGS`` (alerté toujours
sur l'instance hebdo — pas de silence : c'est un rendez-vous fondateur).

Cf. plan ``docs/ARGOS_OPS_PLAN.md`` Annexe D § 1 Direction, Sprint 9.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from loguru import logger

from argos_ops.agents.base import BaseAgent, IOItem, RunResult
from argos_ops.config import REPO_ROOT, get_settings
from argos_ops.crm.db import session_scope
from argos_ops.crm.models import AgentRun
from argos_ops.exceptions import AgentDataSourceError, AgentOutputError
from argos_ops.notifications.discord import GREEN, Embed, EmbedField, send_embed

DEFAULT_OUTPUT_DIR: Path = REPO_ROOT / "data" / "strategy"
WINDOW_DAYS = 7


@dataclass(frozen=True)
class AgentMetric:
    """Métriques 7j d'un agent."""

    agent_name: str
    total_runs: int
    success_runs: int
    failed_runs: int
    skipped_runs: int

    @property
    def success_rate(self) -> float:
        if self.total_runs == 0:
            return 0.0
        return self.success_runs / self.total_runs


@dataclass(frozen=True)
class StrategyReport:
    """Résultat agrégé du run StrategyBot."""

    iso_year: int
    iso_week: int
    metrics: list[AgentMetric]
    total_runs: int
    digest_path: Path
    summary: str


# =============================================================================
# Agrégation
# =============================================================================
def aggregate(runs: list[AgentRun]) -> list[AgentMetric]:
    """Aggrège ``runs`` par agent_name."""
    by_agent: dict[str, dict[str, int]] = {}
    for run in runs:
        bucket = by_agent.setdefault(
            run.agent_name,
            {"total": 0, "success": 0, "failed": 0, "skipped": 0},
        )
        bucket["total"] += 1
        if run.status == "success":
            bucket["success"] += 1
        elif run.status == "failed":
            bucket["failed"] += 1
        elif run.status and run.status.startswith("skipped"):
            bucket["skipped"] += 1
        elif run.status == "killed_by_breaker":
            bucket["failed"] += 1
    out = [
        AgentMetric(
            agent_name=name,
            total_runs=b["total"],
            success_runs=b["success"],
            failed_runs=b["failed"],
            skipped_runs=b["skipped"],
        )
        for name, b in by_agent.items()
    ]
    out.sort(key=lambda m: m.total_runs, reverse=True)
    return out


# =============================================================================
# Génération markdown
# =============================================================================
def render_digest(
    metrics: list[AgentMetric],
    *,
    iso_year: int,
    iso_week: int,
    window_start: datetime,
    window_end: datetime,
) -> str:
    """Rend le digest markdown."""
    lines = [
        f"# StrategyBot — Digest semaine {iso_year}-W{iso_week:02d}",
        "",
        f"Fenêtre : {window_start.date().isoformat()} → {window_end.date().isoformat()}",
        "",
        "## Volume agents",
        "",
        "| Agent | Total | Success | Failed | Skipped | Taux succès |",
        "|-------|-------|---------|--------|---------|-------------|",
    ]
    for m in metrics:
        lines.append(
            f"| {m.agent_name} | {m.total_runs} | {m.success_runs} | "
            f"{m.failed_runs} | {m.skipped_runs} | {m.success_rate * 100:.1f}% |"
        )
    if not metrics:
        lines.append("| _aucun run dans la fenêtre_ | 0 | 0 | 0 | 0 | n/a |")

    total = sum(m.total_runs for m in metrics)
    total_fail = sum(m.failed_runs for m in metrics)
    lines.extend(
        [
            "",
            f"**Total** : {total} runs · {total_fail} failed",
            "",
            "## Signaux stratégiques",
            "",
        ]
    )
    if not metrics:
        lines.append("- Aucune activité agent cette semaine — vérifier l'orchestrator.")
    else:
        top = metrics[0]
        lines.append(
            f"- Bot le plus actif : **{top.agent_name}** "
            f"({top.total_runs} runs, {top.success_rate * 100:.1f}% succès)"
        )
        worst = min(metrics, key=lambda m: m.success_rate)
        if worst.success_rate < 0.9 and worst.total_runs >= 3:
            lines.append(
                f"- Bot à surveiller : **{worst.agent_name}** "
                f"({worst.success_rate * 100:.1f}% succès sur {worst.total_runs} runs)"
            )

    lines.extend(
        [
            "",
            "## TODO fondateur",
            "",
            "- [ ] Lire les recommendations ads de la semaine (`data/ads/recommendations/`)",
            "- [ ] Trier les drafts content en attente (`data/content/drafts/`)",
            "- [ ] Décisions structurantes à logger (`/log-decision`) ?",
            "",
            "_Généré par StrategyBot · P22.E Direction Sprint 9._",
            "",
        ]
    )
    return "\n".join(lines)


# =============================================================================
# Agent
# =============================================================================
class StrategyBot(BaseAgent):
    """VP Stratégie — digest hebdo KPIs."""

    name = "StrategyBot"
    command = "/run-strategy-digest"
    breaker_name = None
    ai_act_risk_class = "limited"

    def __init__(
        self,
        *,
        output_dir: Path = DEFAULT_OUTPUT_DIR,
        window_days: int = WINDOW_DAYS,
        now: datetime | None = None,
    ) -> None:
        self._output_dir = output_dir
        self._window_days = window_days
        self._now = now or datetime.now(UTC)

    async def _fetch_runs(self, cutoff: datetime) -> list[AgentRun]:
        """Lit ``agent_runs`` sur la fenêtre."""
        from sqlmodel import col, select

        async with session_scope() as session:
            stmt = select(AgentRun).where(col(AgentRun.started_at) >= cutoff)
            return list((await session.execute(stmt)).scalars().all())

    async def run(self) -> RunResult:
        cutoff = self._now - timedelta(days=self._window_days)
        try:
            runs = await self._fetch_runs(cutoff)
        except Exception as exc:
            raise AgentDataSourceError(f"db read agent_runs: {exc}") from exc

        metrics = aggregate(runs)
        iso_year, iso_week, _ = self._now.isocalendar()
        body = render_digest(
            metrics,
            iso_year=iso_year,
            iso_week=iso_week,
            window_start=cutoff,
            window_end=self._now,
        )
        try:
            self._output_dir.mkdir(parents=True, exist_ok=True)
            digest_path = self._output_dir / f"digest-{iso_year}-W{iso_week:02d}.md"
            digest_path.write_text(body, encoding="utf-8")
        except OSError as exc:
            raise AgentOutputError(f"write digest: {exc}") from exc

        # Push Embed Discord (toujours — rendez-vous hebdo).
        # Mode dégradé : si le webhook est absent ou que le push échoue,
        # on continue — le markdown sur disque reste la source de vérité.
        settings = get_settings()
        webhook = settings.discord_webhook_ops_logs
        total = sum(m.total_runs for m in metrics)
        discord_pushed = False
        if webhook is None:
            logger.warning(
                "StrategyBot — DISCORD_WEBHOOK_OPS_LOGS absent, "
                "digest écrit sur disque uniquement (mode dégradé)"
            )
        else:
            embed = Embed(
                title=f"StrategyBot — Semaine {iso_year}-W{iso_week:02d}",
                description=f"{total} runs · {len(metrics)} agents actifs",
                color=GREEN,
                fields=[
                    EmbedField(
                        name=m.agent_name,
                        value=f"{m.total_runs} runs · {m.success_rate * 100:.0f}% succès",
                        inline=True,
                    )
                    for m in metrics[:9]
                ],
                footer="Argos Ops • StrategyBot",
                timestamp=self._now.isoformat(),
            )
            try:
                await send_embed(webhook, embed)
                discord_pushed = True
            except Exception as exc:
                logger.warning(f"StrategyBot — push Discord échoué (digest OK sur disque): {exc}")

        try:
            digest_ref = digest_path.relative_to(REPO_ROOT).as_posix()
        except ValueError:
            digest_ref = None
        total_fail = sum(m.failed_runs for m in metrics)
        inputs = [
            IOItem(
                label="Runs agents (agent_runs, 7j)",
                kind="db",
                detail=f"fenêtre {self._window_days}j · {len(metrics)} agents actifs",
                count=total,
            )
        ]
        outputs: list[IOItem] = [
            IOItem(
                label="Digest stratégie hebdo",
                kind="file",
                detail=f"{total} runs · {total_fail} failed",
                ref=digest_ref,
            )
        ]
        if discord_pushed:
            outputs.append(
                IOItem(
                    label="Résumé poussé sur Discord",
                    kind="discord",
                    detail=f"{total} runs · {len(metrics)} agents actifs",
                )
            )
        return RunResult(
            status="success",
            output_summary=f"digest écrit dans {digest_path.name} ({total} runs)",
            inputs=inputs,
            outputs=outputs,
            extras={
                "digest_path": str(digest_path),
                "total_runs": total,
                "discord_pushed": discord_pushed,
            },
        )


__all__ = [
    "DEFAULT_OUTPUT_DIR",
    "WINDOW_DAYS",
    "AgentMetric",
    "StrategyBot",
    "StrategyReport",
    "aggregate",
    "render_digest",
]
