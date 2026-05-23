"""ChurnPredictor — Retention Manager (P22.G CS Sprint 7).

Détecte les signaux pré-churn et calcule un ``risk_score`` 0-100 par
compte via ``argos_ops.cs.scoring.detect_churn_signals``. Écrit
``data/churn/at_risk_<YYYY-MM-DD>.yaml`` + Discord rouge si ≥ 1 compte à
``risk_score ≥ 60``.

Signaux cumulatifs :
- inactivité (≥ 14j jaune, ≥ 30j rouge)
- NPS détracteur (≤ 6)
- tickets 30j (friction)
- sous-utilisation (< 10% du quota)

Le founder traite à la main : appel proactif au compte ≥ 60, mail
empathique au compte 30-60. Idempotent.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

import yaml
from loguru import logger

from argos_ops.agents.base import BaseAgent, RunResult
from argos_ops.config import REPO_ROOT, get_settings
from argos_ops.cs.loader import load_customers
from argos_ops.cs.models import ChurnSignal
from argos_ops.cs.scoring import detect_churn_signals
from argos_ops.notifications.discord import (
    GREEN,
    RED,
    YELLOW,
    Embed,
    EmbedField,
    send_embed,
)

DEFAULT_CUSTOMERS_PATH: Path = REPO_ROOT / "data" / "cs" / "customers.yaml"
DEFAULT_SNAPSHOTS_DIR: Path = REPO_ROOT / "data" / "churn"

URGENT_RISK_THRESHOLD = 60  # score ≥ 60 → action proactive sous 48h


@dataclass
class ChurnReport:
    customers_seen: int = 0
    at_risk: list[ChurnSignal] = field(default_factory=list)
    urgent: list[ChurnSignal] = field(default_factory=list)

    def summary(self) -> str:
        return (
            f"customers={self.customers_seen} at_risk={len(self.at_risk)} "
            f"urgent={len(self.urgent)}"
        )


def _persist_snapshot(snapshot_path: Path, signals: list[ChurnSignal], *, day: date) -> None:
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = {
        "snapshot_date": day.isoformat(),
        "at_risk": [
            {
                "customer_id": s.customer_id,
                "risk_score": s.risk_score,
                "signals": s.signals,
            }
            for s in signals
        ],
    }
    snapshot_path.write_text(
        yaml.safe_dump(payload, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )


def build_churn_embed(report: ChurnReport) -> Embed:
    if report.urgent:
        color = RED
    elif report.at_risk:
        color = YELLOW
    else:
        color = GREEN
    fields = [
        EmbedField(name="Clients vus", value=str(report.customers_seen), inline=True),
        EmbedField(name="À risque", value=str(len(report.at_risk)), inline=True),
        EmbedField(name="Urgents (≥ 60)", value=str(len(report.urgent)), inline=True),
    ]
    if report.urgent:
        lines = [
            f"• [{s.risk_score}/100] **{s.customer_id}** — {'; '.join(s.signals[:3])}"
            for s in report.urgent[:5]
        ]
        fields.append(EmbedField(name="Action proactive 48h", value="\n".join(lines), inline=False))
    elif report.at_risk:
        lines = [
            f"• [{s.risk_score}/100] **{s.customer_id}** — {'; '.join(s.signals[:2])}"
            for s in report.at_risk[:5]
        ]
        fields.append(EmbedField(name="À surveiller", value="\n".join(lines), inline=False))
    return Embed(
        title=f"ChurnPredictor — {len(report.urgent)} urgent / {len(report.at_risk)} à risque",
        description=(
            "Appel proactif sous 48h sur les urgents — snapshot `data/churn/at_risk_<date>.yaml`."
            if report.urgent
            else (
                "Comptes à surveiller — pas d'urgence immédiate."
                if report.at_risk
                else "Aucun signal pré-churn détecté."
            )
        ),
        color=color,
        fields=fields,
        footer="Argos Ops • ChurnPredictor",
    )


class ChurnPredictor(BaseAgent):
    """Détecte les signaux pré-churn et score 0-100 chaque compte à risque."""

    name = "ChurnPredictor"
    command = "/run-churn-predict"
    breaker_name = "ChurnPredictor"

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
            logger.info(f"ChurnPredictor — aucun client ({self._customers_path})")
            return RunResult(status="success", output_summary="silence (no customers)")

        signals = [s for s in (detect_churn_signals(c) for c in customers) if s is not None]
        signals.sort(key=lambda s: s.risk_score, reverse=True)
        urgent = [s for s in signals if s.risk_score >= URGENT_RISK_THRESHOLD]
        report = ChurnReport(customers_seen=len(customers), at_risk=signals, urgent=urgent)

        today = date.today()
        snapshot_path = self._snapshots_dir / f"at_risk_{today.isoformat()}.yaml"
        _persist_snapshot(snapshot_path, signals, day=today)

        webhook = settings.discord_webhook_ops_logs or settings.discord_webhook_alerts
        if webhook is not None and signals:
            try:
                await send_embed(webhook, build_churn_embed(report))
            except Exception as exc:
                logger.warning(f"ChurnPredictor — notif Discord échouée : {exc}")

        return RunResult(status="success", output_summary=report.summary())


__all__ = [
    "DEFAULT_CUSTOMERS_PATH",
    "DEFAULT_SNAPSHOTS_DIR",
    "URGENT_RISK_THRESHOLD",
    "ChurnPredictor",
    "ChurnReport",
    "build_churn_embed",
]
