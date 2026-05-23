"""ContractDeadlineBot — Legal Ops (P22.E Compliance Sprint 8).

Lit ``data/contracts/clients.yaml`` et alerte Discord 60 jours avant
chaque renouvellement de contrat client (date d'anniversaire selon la
clause de reconduction tacite). Permet au fondateur de :

1. Préparer une upsell / négociation
2. Notifier la résiliation avant tacite reconduction si nécessaire

Politique anti-spam :
- **Silence** Discord si aucun contrat n'est dans la fenêtre 60j
- **Embed jaune** si ≥1 contrat dans la fenêtre 30-60j
- **Embed rouge** si ≥1 contrat dans la fenêtre < 30j (urgent)

Cf. plan ``docs/ARGOS_OPS_PLAN.md`` Annexe D § 9 Compliance, Sprint 8.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Literal

import yaml

from argos_ops.agents._watcher_base import color_title, emit_alert_or_silence
from argos_ops.agents.base import BaseAgent, RunResult
from argos_ops.compliance import days_until, next_renewal_date
from argos_ops.config import REPO_ROOT
from argos_ops.notifications.discord import GREEN, RED, YELLOW, Embed, EmbedField

DEFAULT_CONTRACTS_PATH: Path = REPO_ROOT / "data" / "contracts" / "clients.yaml"
WARN_WINDOW_DAYS = 60
URGENT_WINDOW_DAYS = 30

DeadlineStatus = Literal["ok", "warn", "urgent", "expired"]


@dataclass(frozen=True)
class ContractRenewal:
    """Un contrat client + sa prochaine échéance calculée."""

    client: str
    start: date
    term_months: int
    next_renewal: date
    days_left: int
    status: DeadlineStatus
    notes: str | None


@dataclass(frozen=True)
class ContractDeadlineReport:
    """Résultat agrégé du run ContractDeadlineBot."""

    renewals: list[ContractRenewal]
    should_alert: bool
    alert_color: int
    summary: str


# =============================================================================
# Lecture YAML
# =============================================================================
def _parse_date(value: object) -> date | None:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        try:
            return date.fromisoformat(value)
        except ValueError:
            return None
    return None


def _classify(days_left: int) -> DeadlineStatus:
    if days_left < 0:
        return "expired"
    if days_left <= URGENT_WINDOW_DAYS:
        return "urgent"
    if days_left <= WARN_WINDOW_DAYS:
        return "warn"
    return "ok"


def load_contracts(
    path: Path = DEFAULT_CONTRACTS_PATH, *, today: date | None = None
) -> list[ContractRenewal]:
    """Lit le YAML et calcule la prochaine échéance + statut pour chaque contrat.

    Format attendu ::

        contracts:
          - client: "Acme Corp"
            start: "2025-01-15"
            term_months: 12
            notes: "MSA + annexe pentest annuel"
    """
    today = today or datetime.now(UTC).date()
    if not path.exists():
        return []
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    rows = raw.get("contracts", []) or []
    out: list[ContractRenewal] = []
    for row in rows:
        client = row.get("client")
        start = _parse_date(row.get("start"))
        term_months = row.get("term_months")
        if not (client and start and isinstance(term_months, int) and term_months > 0):
            continue
        next_date = next_renewal_date(
            start=start, term_months=term_months, today=today
        )
        left = days_until(next_date, today=today)
        out.append(
            ContractRenewal(
                client=client,
                start=start,
                term_months=term_months,
                next_renewal=next_date,
                days_left=left,
                status=_classify(left),
                notes=row.get("notes"),
            )
        )
    return out


# =============================================================================
# Décision
# =============================================================================
def build_report(renewals: list[ContractRenewal]) -> ContractDeadlineReport:
    has_urgent = any(r.status == "urgent" for r in renewals)
    has_warn = any(r.status == "warn" for r in renewals)
    should_alert = has_urgent or has_warn

    if has_urgent:
        alert_color = RED
    elif has_warn:
        alert_color = YELLOW
    else:
        alert_color = GREEN

    counts = {
        "ok": sum(1 for r in renewals if r.status == "ok"),
        "warn": sum(1 for r in renewals if r.status == "warn"),
        "urgent": sum(1 for r in renewals if r.status == "urgent"),
        "expired": sum(1 for r in renewals if r.status == "expired"),
    }
    summary = (
        f"{counts['ok']} ok · {counts['warn']} warn · "
        f"{counts['urgent']} URGENT · {counts['expired']} expired "
        f"(total {len(renewals)})"
    )
    return ContractDeadlineReport(
        renewals=renewals,
        should_alert=should_alert,
        alert_color=alert_color,
        summary=summary,
    )


# =============================================================================
# Formatting
# =============================================================================
_STATUS_ICON: dict[DeadlineStatus, str] = {
    "ok": "[OK]",
    "warn": "[WRN]",
    "urgent": "[URG]",
    "expired": "[EXP]",
}


def _format_renewal(r: ContractRenewal) -> str:
    lines = [
        f"renouvelle {r.next_renewal.isoformat()} (J{r.days_left:+d})",
        f"terme {r.term_months}m · début {r.start.isoformat()}",
    ]
    if r.notes:
        lines.append(r.notes[:160])
    return " · ".join(lines)


def build_contract_embed(
    report: ContractDeadlineReport, *, now: datetime | None = None
) -> Embed:
    """Embed Discord — un field par contrat warn/urgent/expired."""
    now = now or datetime.now(UTC)
    flagged = [r for r in report.renewals if r.status != "ok"]
    flagged.sort(key=lambda r: r.days_left)
    fields = [
        EmbedField(
            name=f"{_STATUS_ICON[r.status]} {r.client}",
            value=_format_renewal(r),
            inline=False,
        )
        for r in flagged[:15]
    ]
    title_status = color_title(report.alert_color, green=GREEN, yellow=YELLOW, red=RED)
    return Embed(
        title=f"ContractDeadlineBot — {title_status}",
        description=report.summary,
        color=report.alert_color,
        fields=fields,
        footer="Argos Ops • ContractDeadlineBot",
        timestamp=now.isoformat(),
    )


# =============================================================================
# Agent
# =============================================================================
class ContractDeadlineBot(BaseAgent):
    """Legal Ops — alerte 60j avant tacite reconduction."""

    name = "ContractDeadlineBot"
    command = "/run-contract-deadlines"
    breaker_name = None
    ai_act_risk_class = "minimal"

    def __init__(
        self,
        *,
        contracts_path: Path = DEFAULT_CONTRACTS_PATH,
        today: date | None = None,
    ) -> None:
        self._contracts_path = contracts_path
        self._today = today

    async def run(self) -> RunResult:
        renewals = load_contracts(self._contracts_path, today=self._today)
        report = build_report(renewals)
        return await emit_alert_or_silence(
            report, embed_builder=build_contract_embed, agent_name=self.name
        )


__all__ = [
    "DEFAULT_CONTRACTS_PATH",
    "URGENT_WINDOW_DAYS",
    "WARN_WINDOW_DAYS",
    "ContractDeadlineBot",
    "ContractDeadlineReport",
    "ContractRenewal",
    "DeadlineStatus",
    "build_contract_embed",
    "build_report",
    "load_contracts",
]
