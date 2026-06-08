"""HealthScoreBot — CS Ops (P22.G CS Sprint 7).

Calcule un score santé 0-100 par compte à partir de :
- usage (saturation quota ou sous-utilisation)
- tickets 30j (friction)
- NPS (sentiment)
- inactivité (login récent)

Écrit ``data/health_scores/snapshot_<YYYY-MM-DD>.yaml`` (idempotent —
re-lancer le même jour écrase le snapshot). Discord :
- silence si tout vert
- jaune si ≥ 1 compte en bande YELLOW
- rouge si ≥ 1 compte en bande RED (signal pré-churn)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

import yaml
from loguru import logger

from argos_ops.agents.base import BaseAgent, IOItem, RunResult
from argos_ops.config import REPO_ROOT, get_settings
from argos_ops.cs.loader import load_customers
from argos_ops.cs.models import HealthBand, HealthScore
from argos_ops.cs.scoring import compute_health_score
from argos_ops.notifications.discord import (
    GREEN,
    RED,
    YELLOW,
    Embed,
    EmbedField,
    send_embed,
)

DEFAULT_CUSTOMERS_PATH: Path = REPO_ROOT / "data" / "cs" / "customers.yaml"
DEFAULT_SNAPSHOTS_DIR: Path = REPO_ROOT / "data" / "health_scores"


@dataclass
class HealthReport:
    scores: list[HealthScore]
    green: int = 0
    yellow: int = 0
    red: int = 0
    average: int = 0
    worst: list[HealthScore] = field(default_factory=list)

    def summary(self) -> str:
        return (
            f"customers={len(self.scores)} green={self.green} yellow={self.yellow} "
            f"red={self.red} avg={self.average}"
        )


def build_report(scores: list[HealthScore]) -> HealthReport:
    report = HealthReport(scores=scores)
    if not scores:
        return report
    for s in scores:
        if s.band == HealthBand.GREEN:
            report.green += 1
        elif s.band == HealthBand.YELLOW:
            report.yellow += 1
        else:
            report.red += 1
    report.average = round(sum(s.score for s in scores) / len(scores))
    report.worst = sorted(scores, key=lambda s: s.score)[:3]
    return report


def _persist_snapshot(snapshot_path: Path, scores: list[HealthScore], *, day: date) -> None:
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = {
        "snapshot_date": day.isoformat(),
        "scores": [
            {
                "customer_id": s.customer_id,
                "score": s.score,
                "band": s.band.value,
                "drivers": s.drivers,
            }
            for s in scores
        ],
    }
    snapshot_path.write_text(
        yaml.safe_dump(payload, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )


def build_health_embed(report: HealthReport) -> Embed:
    if report.red > 0:
        color = RED
    elif report.yellow > 0:
        color = YELLOW
    else:
        color = GREEN
    fields = [
        EmbedField(name="Total clients", value=str(len(report.scores)), inline=True),
        EmbedField(name="Vert", value=str(report.green), inline=True),
        EmbedField(name="Jaune", value=str(report.yellow), inline=True),
        EmbedField(name="Rouge", value=str(report.red), inline=True),
        EmbedField(name="Score moyen", value=f"{report.average}/100", inline=True),
    ]
    if report.worst and (report.yellow > 0 or report.red > 0):
        lines = [
            f"• [{s.score}/100 {s.band.value}] **{s.customer_id}** — {'; '.join(s.drivers[:3])}"
            for s in report.worst
            if s.band != HealthBand.GREEN
        ]
        if lines:
            fields.append(EmbedField(name="À surveiller", value="\n".join(lines), inline=False))
    return Embed(
        title=f"HealthScoreBot — {report.red} rouge / {report.yellow} jaune / {report.green} vert",
        description=(
            f"Score santé moyen : {report.average}/100."
            if report.scores
            else "Aucun client à scorer."
        ),
        color=color,
        fields=fields,
        footer="Argos Ops • HealthScoreBot",
    )


class HealthScoreBot(BaseAgent):
    """Score santé compte (usage + tickets + NPS + inactivité)."""

    name = "HealthScoreBot"
    command = "/run-health-scores"
    breaker_name = "HealthScoreBot"
    ai_act_risk_class = "minimal"

    def __init__(
        self,
        *,
        customers_path: Path = DEFAULT_CUSTOMERS_PATH,
        snapshots_dir: Path = DEFAULT_SNAPSHOTS_DIR,
    ) -> None:
        self._customers_path = customers_path
        self._snapshots_dir = snapshots_dir

    async def run(self) -> RunResult:
        settings = get_settings()
        customers = load_customers(self._customers_path)
        if not customers:
            logger.info(f"HealthScoreBot — aucun client ({self._customers_path})")
            return RunResult(status="success", output_summary="silence (no customers)")

        scores = [compute_health_score(c) for c in customers]
        today = date.today()
        snapshot_path = self._snapshots_dir / f"snapshot_{today.isoformat()}.yaml"
        _persist_snapshot(snapshot_path, scores, day=today)

        report = build_report(scores)
        webhook = settings.discord_webhook_ops_logs or settings.discord_webhook_alerts
        if webhook is not None and (report.yellow > 0 or report.red > 0):
            try:
                await send_embed(webhook, build_health_embed(report))
            except Exception as exc:
                logger.warning(f"HealthScoreBot — notif Discord échouée : {exc}")

        inputs = [
            IOItem(
                label="Comptes clients",
                kind="file",
                detail="usage · tickets 30j · NPS · inactivité",
                ref="data/cs/customers.yaml",
                count=len(customers),
            )
        ]
        outputs: list[IOItem] = [
            IOItem(
                label="Snapshot scores santé",
                kind="file",
                detail=(
                    f"vert={report.green} jaune={report.yellow} "
                    f"rouge={report.red} · moyenne {report.average}/100"
                ),
                ref=f"data/health_scores/{snapshot_path.name}",
                count=len(scores),
            )
        ]
        if report.red > 0 or report.yellow > 0:
            outputs.append(
                IOItem(
                    label="Alerte Discord comptes à surveiller",
                    kind="discord",
                    count=report.red + report.yellow,
                )
            )

        return RunResult(
            status="success",
            output_summary=report.summary(),
            inputs=inputs,
            outputs=outputs,
        )


__all__ = [
    "DEFAULT_CUSTOMERS_PATH",
    "DEFAULT_SNAPSHOTS_DIR",
    "HealthReport",
    "HealthScoreBot",
    "build_health_embed",
    "build_report",
]
