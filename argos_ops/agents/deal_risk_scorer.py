"""DealRiskScorer — Sales Manager (P22.H Sales Sprint 3).

Lit le pipe ``data/sales/deals/pipe.yaml`` (saisi à la main par le
fondateur, mis à jour après chaque interaction client) et score chaque
deal via :func:`argos_ops.sales.scoring.score_deal_risk`. Discord
notification résumant les deals stalled + top 3 par risk_score.

Format YAML attendu ::

    deals:
      - deal_id: "acme-q2-2026"
        company: "Acme SA"
        stage: "demo_done"  # discovery|demo_scheduled|demo_done|proposal_sent|contract_sent|won|lost
        amount_eur: 4200
        last_activity_at: 2026-05-10
        owner: "founder"
        notes: "Marc revient mardi avec son board"

Aucune écriture sur le YAML — read-only. Le bot loggue + alerte Discord.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import yaml
from loguru import logger

from argos_ops.agents.base import BaseAgent, RunResult
from argos_ops.config import REPO_ROOT, get_settings
from argos_ops.notifications.discord import (
    GREEN,
    ORANGE,
    YELLOW,
    Embed,
    EmbedField,
    send_embed,
)
from argos_ops.sales.models import Deal, DealStage, DealStalledFlag
from argos_ops.sales.scoring import score_deal_risk

DEFAULT_PIPE_PATH: Path = REPO_ROOT / "data" / "sales" / "deals" / "pipe.yaml"


@dataclass
class DealReport:
    """Récap d'un run."""

    total: int = 0
    active: int = 0
    won: int = 0
    lost: int = 0
    stalled: int = 0
    top_risk: list[DealStalledFlag] = field(default_factory=list)

    def summary(self) -> str:
        return (
            f"total={self.total} active={self.active} stalled={self.stalled} "
            f"won={self.won} lost={self.lost}"
        )


def _load_pipe(path: Path) -> list[Deal]:
    if not path.exists():
        return []
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    deals_raw = raw.get("deals", [])
    out: list[Deal] = []
    for entry in deals_raw:
        last_raw = entry["last_activity_at"]
        last = last_raw if isinstance(last_raw, date) else date.fromisoformat(str(last_raw))
        stage = DealStage(entry["stage"])
        out.append(
            Deal(
                deal_id=entry["deal_id"],
                company=entry["company"],
                stage=stage,
                amount_eur=int(entry.get("amount_eur", 0)),
                last_activity_at=last,
                owner=entry.get("owner", "founder"),
                notes=entry.get("notes"),
            )
        )
    return out


def build_risk_report(deals: list[Deal], *, today: date | None = None) -> DealReport:
    report = DealReport(total=len(deals))
    flags: list[DealStalledFlag] = []
    for deal in deals:
        if deal.stage == DealStage.WON:
            report.won += 1
            continue
        if deal.stage == DealStage.LOST:
            report.lost += 1
            continue
        report.active += 1
        flag = score_deal_risk(deal, today=today)
        flags.append(flag)
        if flag.is_stalled:
            report.stalled += 1
    flags.sort(key=lambda f: f.risk_score, reverse=True)
    report.top_risk = flags[:3]
    return report


def build_risk_embed(report: DealReport) -> Embed:
    if report.stalled > 0:
        color = ORANGE
    elif report.active > 0:
        color = YELLOW
    else:
        color = GREEN
    fields = [
        EmbedField(name="Total deals", value=str(report.total), inline=True),
        EmbedField(name="Actifs", value=str(report.active), inline=True),
        EmbedField(name="Stalled", value=str(report.stalled), inline=True),
        EmbedField(name="Won", value=str(report.won), inline=True),
        EmbedField(name="Lost", value=str(report.lost), inline=True),
    ]
    if report.top_risk:
        lines = []
        for flag in report.top_risk:
            lines.append(
                f"• [{flag.risk_score}/100] **{flag.deal.company}** "
                f"({flag.deal.stage.value}) — {flag.reason}"
            )
        fields.append(EmbedField(name="Top risque", value="\n".join(lines), inline=False))
    return Embed(
        title=f"DealRiskScorer — {report.stalled} stalled / {report.active} actifs",
        description=(
            "Relance les deals stalled prioritairement (top risque ci-dessous)."
            if report.stalled > 0
            else "Pipe propre, aucun deal stalled au-delà du seuil."
        ),
        color=color,
        fields=fields,
        footer="Argos Ops • DealRiskScorer",
    )


class DealRiskScorer(BaseAgent):
    """Score le pipe + flag les deals stalled > seuil par stade."""

    name = "DealRiskScorer"
    command = "/run-deal-scoring"
    breaker_name = "DealRiskScorer"

    def __init__(self, *, pipe_path: Path = DEFAULT_PIPE_PATH) -> None:
        self._pipe_path = pipe_path

    async def run(self) -> RunResult:
        settings = get_settings()
        deals = _load_pipe(self._pipe_path)
        if not deals:
            logger.info(f"DealRiskScorer — pipe vide ({self._pipe_path})")
            return RunResult(status="success", output_summary="silence (no deals)")

        report = build_risk_report(deals)
        webhook = settings.discord_webhook_ops_logs or settings.discord_webhook_alerts
        if webhook is not None:
            try:
                await send_embed(webhook, build_risk_embed(report))
            except Exception as exc:
                logger.warning(f"DealRiskScorer — notif Discord échouée : {exc}")

        return RunResult(status="success", output_summary=report.summary())


__all__ = [
    "DEFAULT_PIPE_PATH",
    "DealReport",
    "DealRiskScorer",
    "build_risk_embed",
    "build_risk_report",
]
