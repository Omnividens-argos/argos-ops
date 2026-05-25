"""ReconcileBot — Comptable (Sprint 10).

Rapproche les payouts Stripe avec les crédits Qonto. Le founder fournit :

- ``data/finance/stripe_payouts.yaml`` — liste des payouts (export
  manuel depuis Stripe Dashboard) :

  .. code-block:: yaml

      payouts:
        - id: po_xxx
          arrival_date: 2026-05-20
          amount_eur: 1234.56

- ``data/expenses/<YYYY-MM>.csv`` — export Qonto le plus récent
  (mêmes fichiers que :mod:`argos_ops.agents.expense_auditor`).

Politique alerte :
- **silence (vert)** si tous les payouts ont un match Qonto.
- **embed jaune** si ≥1 crédit Qonto Stripe sans payout correspondant
  (potentiel virement test, remboursement, ou export Stripe incomplet).
- **embed rouge** si ≥1 payout Stripe orphelin (le founder doit
  vérifier le compte Qonto manuellement — fonds peut-être bloqués).

Pas de breaker dédié — c'est un audit, pas un kill switch.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

import yaml
from loguru import logger

from argos_ops.agents._watcher_base import color_title, emit_alert_or_silence
from argos_ops.agents.base import BaseAgent, RunResult
from argos_ops.agents.expense_auditor import find_latest_csv
from argos_ops.config import REPO_ROOT
from argos_ops.exceptions import AgentDataSourceError
from argos_ops.finance.expense_csv import parse_qonto_csv
from argos_ops.finance.reconcile import (
    ReconcileReport,
    parse_payouts_yaml_entries,
    reconcile,
)
from argos_ops.notifications.discord import GREEN, RED, YELLOW, Embed, EmbedField

DEFAULT_PAYOUTS_PATH: Path = REPO_ROOT / "data" / "finance" / "stripe_payouts.yaml"
DEFAULT_EXPENSES_DIR: Path = REPO_ROOT / "data" / "expenses"

ReconcileSeverity = Literal["ok", "warn", "alert"]


@dataclass(frozen=True)
class ReconcileRunReport:
    """Résultat agrégé du run ReconcileBot."""

    report: ReconcileReport
    severity: ReconcileSeverity
    should_alert: bool
    alert_color: int
    summary: str


def load_payouts_yaml(path: Path) -> list[dict[str, object]]:
    """Lit le YAML payouts, retourne ``[]`` si absent ou mal formé."""
    if not path.exists():
        return []
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    entries = raw.get("payouts", [])
    return entries if isinstance(entries, list) else []


def build_run_report(report: ReconcileReport) -> ReconcileRunReport:
    """Classifie la sévérité selon les listes orphelines."""
    if report.orphan_payouts:
        severity: ReconcileSeverity = "alert"
        color = RED
    elif report.orphan_credits:
        severity = "warn"
        color = YELLOW
    else:
        severity = "ok"
        color = GREEN

    should_alert = severity != "ok"
    return ReconcileRunReport(
        report=report,
        severity=severity,
        should_alert=should_alert,
        alert_color=color,
        summary=report.summary(),
    )


def build_reconcile_embed(
    run_report: ReconcileRunReport, *, now: datetime | None = None
) -> Embed:
    """Embed Discord — un field par catégorie orpheline (capped à 5 chacune)."""
    now = now or datetime.now(UTC)
    report = run_report.report
    fields: list[EmbedField] = []

    if report.orphan_payouts:
        lines = [
            f"- {p.id} · {p.arrival_date} · {p.amount_eur} €"
            for p in report.orphan_payouts[:5]
        ]
        if len(report.orphan_payouts) > 5:
            lines.append(f"…+{len(report.orphan_payouts) - 5}")
        fields.append(
            EmbedField(
                name="[ORPH] Payouts Stripe sans crédit Qonto",
                value="\n".join(lines)[:1020],
                inline=False,
            )
        )
    if report.orphan_credits:
        lines = [
            f"- {c.settled_on} · {c.amount_eur} € · {c.vendor}"
            for c in report.orphan_credits[:5]
        ]
        if len(report.orphan_credits) > 5:
            lines.append(f"…+{len(report.orphan_credits) - 5}")
        fields.append(
            EmbedField(
                name="[ORPH] Crédits Qonto Stripe sans payout",
                value="\n".join(lines)[:1020],
                inline=False,
            )
        )

    if not fields:
        fields.append(
            EmbedField(
                name="[OK]",
                value=f"{len(report.matches)} payouts matchés",
                inline=False,
            )
        )

    title_status = color_title(run_report.alert_color, green=GREEN, yellow=YELLOW, red=RED)
    return Embed(
        title=f"ReconcileBot — {title_status}",
        description=run_report.summary,
        color=run_report.alert_color,
        fields=fields,
        footer="Argos Ops • ReconcileBot",
        timestamp=now.isoformat(),
    )


class ReconcileBot(BaseAgent):
    """Comptable — rapproche Stripe payouts ↔ crédits Qonto."""

    name = "ReconcileBot"
    command = "/run-reconcile"
    breaker_name = None
    ai_act_risk_class = "minimal"

    def __init__(
        self,
        *,
        payouts_path: Path = DEFAULT_PAYOUTS_PATH,
        expenses_dir: Path = DEFAULT_EXPENSES_DIR,
    ) -> None:
        self._payouts_path = payouts_path
        self._expenses_dir = expenses_dir

    async def run(self) -> RunResult:
        try:
            payouts_entries = load_payouts_yaml(self._payouts_path)
        except (OSError, UnicodeDecodeError, yaml.YAMLError) as exc:
            raise AgentDataSourceError(
                f"load payouts {self._payouts_path.name}: {exc}"
            ) from exc
        payouts = parse_payouts_yaml_entries(payouts_entries)
        if not payouts:
            logger.info(
                f"ReconcileBot — aucun payout dans {self._payouts_path}, skip"
            )
            return RunResult(
                status="success",
                output_summary="silence (aucun payout)",
                extras={"alerted": False},
            )

        csv = find_latest_csv(self._expenses_dir)
        if csv is None:
            logger.info(
                f"ReconcileBot — aucun CSV Qonto dans {self._expenses_dir}, skip"
            )
            return RunResult(
                status="success",
                output_summary="silence (aucun CSV Qonto)",
                extras={"alerted": False},
            )

        try:
            expenses = parse_qonto_csv(csv)
        except (OSError, UnicodeDecodeError, ValueError) as exc:
            raise AgentDataSourceError(f"parse CSV {csv.name}: {exc}") from exc
        report = reconcile(payouts, expenses)
        run_report = build_run_report(report)
        return await emit_alert_or_silence(
            run_report,
            embed_builder=build_reconcile_embed,
            agent_name=self.name,
        )


__all__ = [
    "DEFAULT_EXPENSES_DIR",
    "DEFAULT_PAYOUTS_PATH",
    "ReconcileBot",
    "ReconcileRunReport",
    "ReconcileSeverity",
    "build_reconcile_embed",
    "build_run_report",
    "load_payouts_yaml",
]
