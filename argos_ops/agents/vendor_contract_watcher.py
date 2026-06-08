"""VendorContractWatcher — Achats (Sprint 10).

Lit ``data/contracts/contracts.yaml`` et alerte Discord si un contrat
fournisseur arrive à échéance dans la fenêtre d'alerte (par défaut
60 jours). Catch les tacites reconductions qu'on oublie d'annuler.

Format YAML ::

    contracts:
      - vendor: OVHcloud
        renewal_date: 2026-09-01
        notice_period_days: 60
        monthly_cost_eur: 12.00
        notes: hébergement omnividens.fr
      - vendor: Stripe
        renewal_date: 2027-01-01
        notice_period_days: 0
        notes: pas de tacite reconduction (commission %)

Le bot calcule, pour chaque contrat, la date butoir d'annulation
(= ``renewal_date - notice_period_days``) et alerte si cette date est
dans la fenêtre courante.

Politique alerte :
- **silence (vert)** si aucun contrat n'a sa date butoir dans :data:`ALERT_WINDOW_DAYS`
- **embed jaune** si ≥1 contrat dont la butoir est entre J et J+30
- **embed rouge** si ≥1 contrat dont la butoir est dépassée (on a raté
  la fenêtre d'annulation — facturation reconduite)

Pas de slash command — cron Task Scheduler hebdo, le founder veut juste
être prévenu à temps.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Literal

import yaml
from loguru import logger

from argos_ops.agents._watcher_base import color_title, emit_alert_or_silence
from argos_ops.agents.base import BaseAgent, IOItem, RunResult
from argos_ops.config import REPO_ROOT
from argos_ops.exceptions import AgentDataSourceError
from argos_ops.notifications.discord import GREEN, RED, YELLOW, Embed, EmbedField

DEFAULT_CONTRACTS_PATH: Path = REPO_ROOT / "data" / "contracts" / "contracts.yaml"
ALERT_WINDOW_DAYS = 60
URGENT_WINDOW_DAYS = 30

ContractStatus = Literal["ok", "approaching", "urgent", "missed"]


@dataclass(frozen=True)
class Contract:
    """Un contrat fournisseur."""

    vendor: str
    renewal_date: date
    notice_period_days: int
    monthly_cost_eur: Decimal
    notes: str | None
    deadline_date: date  # = renewal_date - notice_period_days
    days_until_deadline: int
    status: ContractStatus


@dataclass(frozen=True)
class ContractReport:
    """Bilan d'un run VendorContractWatcher."""

    contracts: list[Contract]
    should_alert: bool
    alert_color: int
    summary: str


def _parse_date(raw: object) -> date | None:
    if isinstance(raw, datetime):
        return raw.date()
    if isinstance(raw, date):
        return raw
    if isinstance(raw, str):
        try:
            return date.fromisoformat(raw)
        except ValueError:
            return None
    return None


def _coerce_cost(raw: object) -> Decimal:
    if raw is None:
        return Decimal("0.00")
    try:
        return Decimal(str(raw))
    except (InvalidOperation, ValueError, TypeError):
        return Decimal("0.00")


def _classify(days_until_deadline: int) -> ContractStatus:
    if days_until_deadline < 0:
        return "missed"
    if days_until_deadline <= URGENT_WINDOW_DAYS:
        return "urgent"
    if days_until_deadline <= ALERT_WINDOW_DAYS:
        return "approaching"
    return "ok"


def load_contracts(
    path: Path = DEFAULT_CONTRACTS_PATH, *, today: date | None = None
) -> list[Contract]:
    """Lit le YAML et calcule status / deadline pour chaque contrat."""
    today = today or datetime.now(UTC).date()
    if not path.exists():
        return []
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    rows = raw.get("contracts", []) or []
    out: list[Contract] = []
    for row in rows:
        vendor = row.get("vendor")
        renewal = _parse_date(row.get("renewal_date"))
        if not vendor or renewal is None:
            continue
        notice = int(row.get("notice_period_days", 0) or 0)
        deadline = renewal - timedelta(days=notice)
        days_until = (deadline - today).days
        out.append(
            Contract(
                vendor=vendor,
                renewal_date=renewal,
                notice_period_days=notice,
                monthly_cost_eur=_coerce_cost(row.get("monthly_cost_eur")),
                notes=row.get("notes"),
                deadline_date=deadline,
                days_until_deadline=days_until,
                status=_classify(days_until),
            )
        )
    return out


def build_report(contracts: list[Contract]) -> ContractReport:
    """Sévérité agrégée + summary court."""
    has_missed = any(c.status == "missed" for c in contracts)
    has_urgent = any(c.status == "urgent" for c in contracts)
    has_approaching = any(c.status == "approaching" for c in contracts)
    should_alert = has_missed or has_urgent or has_approaching

    if has_missed or has_urgent:
        color = RED
    elif has_approaching:
        color = YELLOW
    else:
        color = GREEN

    ok = sum(1 for c in contracts if c.status == "ok")
    approaching = sum(1 for c in contracts if c.status == "approaching")
    urgent = sum(1 for c in contracts if c.status == "urgent")
    missed = sum(1 for c in contracts if c.status == "missed")
    summary = (
        f"{ok} ok · {approaching} approaching · "
        f"{urgent} urgent · {missed} missed"
    )

    return ContractReport(
        contracts=contracts,
        should_alert=should_alert,
        alert_color=color,
        summary=summary,
    )


_STATUS_ICON: dict[ContractStatus, str] = {
    "ok": "[OK]",
    "approaching": "[60J]",
    "urgent": "[30J]",
    "missed": "[MISS]",
}


def build_contract_embed(
    report: ContractReport, *, now: datetime | None = None
) -> Embed:
    """Embed Discord — un field par contrat en alerte."""
    now = now or datetime.now(UTC)
    fields = [
        EmbedField(
            name=f"{_STATUS_ICON[c.status]} {c.vendor}",
            value=(
                f"renewal {c.renewal_date} · "
                f"deadline annulation {c.deadline_date} "
                f"(J{c.days_until_deadline:+d}) · "
                f"{c.monthly_cost_eur} €/m"
                + (f" · {c.notes[:120]}" if c.notes else "")
            ),
            inline=False,
        )
        for c in report.contracts
        if c.status != "ok"
    ]
    title_status = color_title(report.alert_color, green=GREEN, yellow=YELLOW, red=RED)
    return Embed(
        title=f"VendorContractWatcher — {title_status}",
        description=report.summary,
        color=report.alert_color,
        fields=fields,
        footer="Argos Ops • VendorContractWatcher",
        timestamp=now.isoformat(),
    )


class VendorContractWatcher(BaseAgent):
    """Achats — alerte avant tacite reconduction fournisseurs."""

    name = "VendorContractWatcher"
    command = None
    breaker_name = None
    ai_act_risk_class = "minimal"

    def __init__(self, *, contracts_path: Path = DEFAULT_CONTRACTS_PATH) -> None:
        self._path = contracts_path

    async def run(self) -> RunResult:
        try:
            contracts = load_contracts(self._path)
        except (OSError, UnicodeDecodeError, yaml.YAMLError) as exc:
            raise AgentDataSourceError(
                f"load contracts {self._path.name}: {exc}"
            ) from exc
        if not contracts:
            logger.info(f"VendorContractWatcher — {self._path} absent ou vide, skip")
            return RunResult(
                status="success",
                output_summary="silence (aucun contrat déclaré)",
                extras={"alerted": False},
            )
        report = build_report(contracts)
        missed = [c for c in contracts if c.status == "missed"]
        urgent = [c for c in contracts if c.status == "urgent"]
        approaching = [c for c in contracts if c.status == "approaching"]
        inputs = [
            IOItem(
                label="Contrats fournisseurs",
                kind="file",
                detail=str(self._path.name),
                ref=str(self._path),
                count=len(contracts),
            ),
        ]
        outputs = [
            IOItem(
                label="Deadlines d'annulation ratées",
                kind="other",
                detail=", ".join(c.vendor for c in missed) or None,
                count=len(missed),
            ),
            IOItem(
                label="Annulations urgentes (≤ 30j)",
                kind="other",
                detail=", ".join(c.vendor for c in urgent) or None,
                count=len(urgent),
            ),
            IOItem(
                label="Annulations approchantes (30-60j)",
                kind="other",
                detail=", ".join(c.vendor for c in approaching) or None,
                count=len(approaching),
            ),
        ]
        return await emit_alert_or_silence(
            report,
            embed_builder=build_contract_embed,
            agent_name=self.name,
            inputs=inputs,
            outputs=outputs,
        )


__all__ = [
    "ALERT_WINDOW_DAYS",
    "DEFAULT_CONTRACTS_PATH",
    "URGENT_WINDOW_DAYS",
    "Contract",
    "ContractReport",
    "ContractStatus",
    "VendorContractWatcher",
    "build_contract_embed",
    "build_report",
    "load_contracts",
]
