"""ExpenseAuditor — Contrôleur de gestion (Sprint 10).

Parse le CSV Qonto le plus récent dans ``data/expenses/`` et alerte
Discord si des anomalies sont détectées (montants outliers, doublons,
nouveau vendor).

Pas d'API Qonto (D-017). Le founder dépose les exports CSV mensuels :
``data/expenses/2026-05.csv`` (un fichier par mois). Le bot pick le
CSV le plus récent par mtime.

Politique alerte (watcher pattern) :
- **silence (vert)** si 0 anomalie
- **embed jaune** si seulement ``new_vendor`` (potentiel SaaS récurrent
  à enregistrer dans le journal vendor)
- **embed rouge** si ``amount_outlier`` ou ``duplicate`` (besoin de
  vérification rapide — potentiel fraude ou double prélèvement)

Historique vendor : journal markdown auto-maintenu dans
``data/expenses/vendors.md`` (1 ligne par vendor connu). Pas en YAML
pour éviter le diff bruyant — append-only, dedup au load.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from loguru import logger

from argos_ops.agents._watcher_base import color_title, emit_alert_or_silence
from argos_ops.agents.base import BaseAgent, RunResult
from argos_ops.config import REPO_ROOT
from argos_ops.exceptions import AgentDataSourceError
from argos_ops.finance.expense_csv import (
    Anomaly,
    detect_anomalies,
    parse_qonto_csv,
)
from argos_ops.notifications.discord import GREEN, RED, YELLOW, Embed, EmbedField

DEFAULT_EXPENSES_DIR: Path = REPO_ROOT / "data" / "expenses"
VENDORS_JOURNAL_NAME = "vendors.md"

ExpenseAuditSeverity = Literal["ok", "warn", "alert"]


@dataclass(frozen=True)
class ExpenseAuditReport:
    """Résultat agrégé du run ExpenseAuditor."""

    source_csv: Path | None
    anomalies: list[Anomaly]
    severity: ExpenseAuditSeverity
    should_alert: bool
    alert_color: int
    summary: str


def find_latest_csv(directory: Path) -> Path | None:
    """Retourne le CSV mtime-le-plus-récent ou None si rien."""
    if not directory.exists():
        return None
    candidates = [p for p in directory.glob("*.csv") if p.is_file()]
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime)


def load_vendor_history(directory: Path) -> set[str]:
    """Charge la liste des vendors déjà vus (1 par ligne, casse préservée).

    Format markdown auto-maintenu :
    ``# Vendors\n- Acme Corp\n- Foo Ltd\n``
    """
    path = directory / VENDORS_JOURNAL_NAME
    if not path.exists():
        return set()
    vendors: set[str] = set()
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line.startswith("- "):
            vendors.add(line[2:].strip())
    return vendors


def append_new_vendors(directory: Path, new_vendors: set[str]) -> None:
    """Ajoute les vendors inconnus au journal. Idempotent (dedup au load)."""
    if not new_vendors:
        return
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / VENDORS_JOURNAL_NAME
    existing = load_vendor_history(directory)
    to_add = sorted(new_vendors - existing)
    if not to_add:
        return
    header = "# Vendors\n\n" if not path.exists() else ""
    with path.open("a", encoding="utf-8") as fh:
        fh.write(header)
        for v in to_add:
            fh.write(f"- {v}\n")


def build_report(
    source: Path | None, anomalies: list[Anomaly]
) -> ExpenseAuditReport:
    """Classifie la sévérité et compose le summary."""
    if not anomalies:
        return ExpenseAuditReport(
            source_csv=source,
            anomalies=[],
            severity="ok",
            should_alert=False,
            alert_color=GREEN,
            summary=f"{source.name if source else 'aucun CSV'} — 0 anomalie",
        )

    kinds = {a.kind for a in anomalies}
    if kinds == {"new_vendor"}:
        severity: ExpenseAuditSeverity = "warn"
        color = YELLOW
    else:
        severity = "alert"
        color = RED

    by_kind: dict[str, int] = {}
    for a in anomalies:
        by_kind[a.kind] = by_kind.get(a.kind, 0) + 1
    summary_parts = [f"{c} {k}" for k, c in by_kind.items()]
    summary = f"{source.name if source else 'csv'} — {' · '.join(summary_parts)}"
    return ExpenseAuditReport(
        source_csv=source,
        anomalies=anomalies,
        severity=severity,
        should_alert=True,
        alert_color=color,
        summary=summary,
    )


_KIND_ICON: dict[str, str] = {
    "amount_outlier": "[OUT]",
    "duplicate": "[DUP]",
    "new_vendor": "[NEW]",
}


def build_expense_embed(
    report: ExpenseAuditReport, *, now: datetime | None = None
) -> Embed:
    """Construit l'embed Discord — un field par anomalie (capped à 10)."""
    now = now or datetime.now(UTC)
    fields = [
        EmbedField(
            name=f"{_KIND_ICON.get(a.kind, '[?]')} {a.expense.vendor}",
            value=f"{a.expense.settled_on} · {a.expense.amount_eur} € · {a.reason}",
            inline=False,
        )
        for a in report.anomalies[:10]
    ]
    if len(report.anomalies) > 10:
        fields.append(
            EmbedField(
                name="…",
                value=f"+{len(report.anomalies) - 10} anomalies supplémentaires",
                inline=False,
            )
        )
    title_status = color_title(report.alert_color, green=GREEN, yellow=YELLOW, red=RED)
    return Embed(
        title=f"ExpenseAuditor — {title_status}",
        description=report.summary,
        color=report.alert_color,
        fields=fields,
        footer="Argos Ops • ExpenseAuditor",
        timestamp=now.isoformat(),
    )


class ExpenseAuditor(BaseAgent):
    """Contrôleur de gestion — audite le dernier CSV Qonto."""

    name = "ExpenseAuditor"
    command = "/run-expense-audit"
    breaker_name = None
    ai_act_risk_class = "minimal"

    def __init__(self, *, expenses_dir: Path = DEFAULT_EXPENSES_DIR) -> None:
        self._dir = expenses_dir

    async def run(self) -> RunResult:
        source = find_latest_csv(self._dir)
        if source is None:
            logger.info(f"ExpenseAuditor — aucun CSV dans {self._dir}, skip")
            return RunResult(
                status="success",
                output_summary="silence (aucun CSV)",
                extras={"alerted": False},
            )

        try:
            expenses = parse_qonto_csv(source)
        except (OSError, UnicodeDecodeError, ValueError) as exc:
            raise AgentDataSourceError(f"parse CSV {source.name}: {exc}") from exc
        history = load_vendor_history(self._dir)
        anomalies = detect_anomalies(expenses, historic_vendors=history)
        report = build_report(source, anomalies)

        # Met à jour le journal vendors (append-only, idempotent)
        seen_now = {e.vendor for e in expenses}
        append_new_vendors(self._dir, seen_now)

        return await emit_alert_or_silence(
            report, embed_builder=build_expense_embed, agent_name=self.name
        )


__all__ = [
    "DEFAULT_EXPENSES_DIR",
    "VENDORS_JOURNAL_NAME",
    "ExpenseAuditReport",
    "ExpenseAuditSeverity",
    "ExpenseAuditor",
    "append_new_vendors",
    "build_expense_embed",
    "build_report",
    "find_latest_csv",
    "load_vendor_history",
]
