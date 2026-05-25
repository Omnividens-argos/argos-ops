"""BurnRateMonitor — CFO adjoint (Sprint 10).

Lit l'état trésorerie déclaré (``data/finance/treasury_state.yaml``) et
le compare au burn mensuel estimé pour calculer le runway. Alerte
Discord si runway < seuil.

Pas de slash command — cron Task Scheduler hebdo (le founder n'a pas
besoin de regarder le burn en direct, juste d'être prévenu si ça dérape).

YAML attendu ::

    cash_balance_eur: 80000.00
    monthly_burn_eur: 8500.00
    monthly_revenue_eur: 3200.00      # MRR Stripe est plus authoritative
                                       # mais le founder peut override
    snapshot_date: 2026-05-20

Politique alerte :
- **silence (vert)** si runway > :data:`RUNWAY_WARN_MONTHS` (9 mois)
- **embed jaune** si runway entre :data:`RUNWAY_ALERT_MONTHS` (6 mois)
  et :data:`RUNWAY_WARN_MONTHS`
- **embed rouge** si runway < :data:`RUNWAY_ALERT_MONTHS`, ou si
  monthly_burn dépasse le budget mensuel fixé.

Si pas de YAML : skip silencieux (le founder n'a pas encore renseigné).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Literal

import yaml
from loguru import logger

from argos_ops.agents._watcher_base import color_title, emit_alert_or_silence
from argos_ops.agents.base import BaseAgent, RunResult
from argos_ops.config import REPO_ROOT
from argos_ops.exceptions import AgentDataSourceError
from argos_ops.notifications.discord import GREEN, RED, YELLOW, Embed, EmbedField

DEFAULT_TREASURY_PATH: Path = REPO_ROOT / "data" / "finance" / "treasury_state.yaml"
RUNWAY_WARN_MONTHS = Decimal("9")
RUNWAY_ALERT_MONTHS = Decimal("6")
DEFAULT_BURN_CAP_EUR = Decimal("12000.00")
"""Cap mensuel par défaut au-delà duquel on alerte (override via YAML)."""

BurnSeverity = Literal["ok", "warn", "alert"]


@dataclass(frozen=True)
class TreasurySnapshot:
    """Photo de trésorerie déclarée par le founder."""

    cash_balance_eur: Decimal
    monthly_burn_eur: Decimal
    monthly_revenue_eur: Decimal
    snapshot_date: date | None
    burn_cap_eur: Decimal


@dataclass(frozen=True)
class BurnReport:
    """Résultat d'un run BurnRateMonitor."""

    snapshot: TreasurySnapshot | None
    net_burn_eur: Decimal
    runway_months: Decimal | None
    severity: BurnSeverity
    should_alert: bool
    alert_color: int
    summary: str


def _coerce_decimal(value: object, default: Decimal = Decimal("0.00")) -> Decimal:
    if value is None:
        return default
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return default


def load_treasury(path: Path = DEFAULT_TREASURY_PATH) -> TreasurySnapshot | None:
    """Lit le YAML treasury, retourne None si absent."""
    if not path.exists():
        return None
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    snapshot_date_raw = raw.get("snapshot_date")
    if isinstance(snapshot_date_raw, datetime):
        snapshot_date = snapshot_date_raw.date()
    elif isinstance(snapshot_date_raw, date):
        snapshot_date = snapshot_date_raw
    elif isinstance(snapshot_date_raw, str):
        try:
            snapshot_date = date.fromisoformat(snapshot_date_raw)
        except ValueError:
            snapshot_date = None
    else:
        snapshot_date = None

    return TreasurySnapshot(
        cash_balance_eur=_coerce_decimal(raw.get("cash_balance_eur")),
        monthly_burn_eur=_coerce_decimal(raw.get("monthly_burn_eur")),
        monthly_revenue_eur=_coerce_decimal(raw.get("monthly_revenue_eur")),
        snapshot_date=snapshot_date,
        burn_cap_eur=_coerce_decimal(raw.get("burn_cap_eur"), DEFAULT_BURN_CAP_EUR),
    )


def build_report(snapshot: TreasurySnapshot | None) -> BurnReport:
    """Calcule net_burn et runway, classifie la sévérité."""
    if snapshot is None:
        return BurnReport(
            snapshot=None,
            net_burn_eur=Decimal("0.00"),
            runway_months=None,
            severity="ok",
            should_alert=False,
            alert_color=GREEN,
            summary="treasury_state.yaml absent — skip",
        )

    net_burn = snapshot.monthly_burn_eur - snapshot.monthly_revenue_eur
    if net_burn <= 0:
        runway_months: Decimal | None = None  # cash-flow positif
        severity: BurnSeverity = "ok"
        color = GREEN
        summary = (
            f"net_burn={net_burn} (positif) · "
            f"cash={snapshot.cash_balance_eur} €"
        )
    else:
        runway_months = (snapshot.cash_balance_eur / net_burn).quantize(Decimal("0.1"))
        burn_over_cap = snapshot.monthly_burn_eur > snapshot.burn_cap_eur
        if runway_months < RUNWAY_ALERT_MONTHS or burn_over_cap:
            severity = "alert"
            color = RED
        elif runway_months < RUNWAY_WARN_MONTHS:
            severity = "warn"
            color = YELLOW
        else:
            severity = "ok"
            color = GREEN
        summary = (
            f"runway={runway_months}m · net_burn={net_burn} €/m · "
            f"cash={snapshot.cash_balance_eur} €"
        )

    should_alert = severity != "ok"
    return BurnReport(
        snapshot=snapshot,
        net_burn_eur=net_burn,
        runway_months=runway_months,
        severity=severity,
        should_alert=should_alert,
        alert_color=color,
        summary=summary,
    )


def build_burn_embed(report: BurnReport, *, now: datetime | None = None) -> Embed:
    """Embed Discord — toujours appelé en cas d'alerte uniquement."""
    now = now or datetime.now(UTC)
    snap = report.snapshot
    fields: list[EmbedField] = []
    if snap is not None:
        fields.append(
            EmbedField(
                name="Trésorerie",
                value=(
                    f"cash: {snap.cash_balance_eur} €\n"
                    f"burn: {snap.monthly_burn_eur} €/m (cap {snap.burn_cap_eur})\n"
                    f"revenue: {snap.monthly_revenue_eur} €/m"
                ),
                inline=False,
            )
        )
        fields.append(
            EmbedField(
                name="Runway",
                value=(
                    f"{report.runway_months}m"
                    if report.runway_months is not None
                    else "n/a (cash-flow positif)"
                ),
                inline=True,
            )
        )
        if snap.snapshot_date is not None:
            fields.append(
                EmbedField(
                    name="Snapshot",
                    value=snap.snapshot_date.isoformat(),
                    inline=True,
                )
            )
    title_status = color_title(report.alert_color, green=GREEN, yellow=YELLOW, red=RED)
    return Embed(
        title=f"BurnRateMonitor — {title_status}",
        description=report.summary,
        color=report.alert_color,
        fields=fields,
        footer="Argos Ops • BurnRateMonitor",
        timestamp=now.isoformat(),
    )


class BurnRateMonitor(BaseAgent):
    """CFO adjoint — alerte si runway < 9 mois ou burn > cap."""

    name = "BurnRateMonitor"
    command = None  # pas de slash (cron pur)
    breaker_name = None
    ai_act_risk_class = "minimal"

    def __init__(self, *, treasury_path: Path = DEFAULT_TREASURY_PATH) -> None:
        self._path = treasury_path

    async def run(self) -> RunResult:
        try:
            snapshot = load_treasury(self._path)
        except (OSError, UnicodeDecodeError, yaml.YAMLError) as exc:
            raise AgentDataSourceError(
                f"load treasury {self._path.name}: {exc}"
            ) from exc
        report = build_report(snapshot)
        if snapshot is None:
            logger.info(f"BurnRateMonitor — {self._path} absent, skip silencieux")
        return await emit_alert_or_silence(
            report, embed_builder=build_burn_embed, agent_name=self.name
        )


__all__ = [
    "DEFAULT_BURN_CAP_EUR",
    "DEFAULT_TREASURY_PATH",
    "RUNWAY_ALERT_MONTHS",
    "RUNWAY_WARN_MONTHS",
    "BurnRateMonitor",
    "BurnReport",
    "BurnSeverity",
    "TreasurySnapshot",
    "build_burn_embed",
    "build_report",
    "load_treasury",
]
