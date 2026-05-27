"""UpsellSpotter — Account Growth (P22.G CS Sprint 7).

Repère les comptes mûrs pour upsell — usage ≥ 80% du quota plan
(``USAGE_UPSELL_THRESHOLD`` dans ``argos_ops.cs.scoring``). Écrit
``data/upsell/candidates_<YYYY-MM-DD>.yaml`` + alerte Discord si ≥ 1
candidat trouvé.

Le founder traite à la main : pitch upsell par mail/call, propose plan
supérieur en cohérence avec usage observé. Idempotent — snapshot du jour
écrasé à chaque run.
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
from argos_ops.cs.models import UpsellCandidate
from argos_ops.cs.scoring import detect_upsell_candidate
from argos_ops.notifications.discord import (
    GREEN,
    YELLOW,
    Embed,
    EmbedField,
    send_embed,
)

DEFAULT_CUSTOMERS_PATH: Path = REPO_ROOT / "data" / "cs" / "customers.yaml"
DEFAULT_SNAPSHOTS_DIR: Path = REPO_ROOT / "data" / "upsell"


@dataclass
class UpsellReport:
    candidates: list[UpsellCandidate] = field(default_factory=list)
    customers_seen: int = 0

    def summary(self) -> str:
        return f"customers={self.customers_seen} upsell_candidates={len(self.candidates)}"


def _persist_snapshot(snapshot_path: Path, candidates: list[UpsellCandidate], *, day: date) -> None:
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = {
        "snapshot_date": day.isoformat(),
        "candidates": [
            {
                "customer_id": c.customer_id,
                "usage_ratio": c.usage_ratio,
                "suggested_plan": c.suggested_plan.value,
                "reason": c.reason,
            }
            for c in candidates
        ],
    }
    snapshot_path.write_text(
        yaml.safe_dump(payload, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )


def build_upsell_embed(report: UpsellReport) -> Embed:
    color = YELLOW if report.candidates else GREEN
    fields = [
        EmbedField(name="Clients vus", value=str(report.customers_seen), inline=True),
        EmbedField(name="Candidats upsell", value=str(len(report.candidates)), inline=True),
    ]
    if report.candidates:
        lines = [
            f"• **{c.customer_id}** → {c.suggested_plan.value} ({c.usage_ratio:.0%} quota)"
            for c in report.candidates[:6]
        ]
        fields.append(EmbedField(name="Top candidats", value="\n".join(lines), inline=False))
    return Embed(
        title=f"UpsellSpotter — {len(report.candidates)} candidat(s) upsell",
        description=(
            "Pitch upsell par mail/call — snapshot dans `data/upsell/`."
            if report.candidates
            else "Aucun compte saturé aujourd'hui."
        ),
        color=color,
        fields=fields,
        footer="Argos Ops • UpsellSpotter",
    )


class UpsellSpotter(BaseAgent):
    """Détecte les comptes prêts pour upsell (usage ≥ 80% quota plan)."""

    name = "UpsellSpotter"
    command = "/run-upsell-spots"
    breaker_name = "UpsellSpotter"
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
            logger.info(f"UpsellSpotter — aucun client ({self._customers_path})")
            return RunResult(status="success", output_summary="silence (no customers)")

        candidates = [c for c in (detect_upsell_candidate(cu) for cu in customers) if c is not None]
        report = UpsellReport(candidates=candidates, customers_seen=len(customers))

        today = date.today()
        snapshot_path = self._snapshots_dir / f"candidates_{today.isoformat()}.yaml"
        _persist_snapshot(snapshot_path, candidates, day=today)

        webhook = settings.discord_webhook_ops_logs or settings.discord_webhook_alerts
        if webhook is not None and candidates:
            try:
                await send_embed(webhook, build_upsell_embed(report))
            except Exception as exc:
                logger.warning(f"UpsellSpotter — notif Discord échouée : {exc}")

        return RunResult(status="success", output_summary=report.summary())


__all__ = [
    "DEFAULT_CUSTOMERS_PATH",
    "DEFAULT_SNAPSHOTS_DIR",
    "UpsellReport",
    "UpsellSpotter",
    "build_upsell_embed",
]
