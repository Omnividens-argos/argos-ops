"""``ExpenseAuditorScript`` — audit dépenses Qonto (Finance, archi v2, S5).

Bras déterministe : audite le dernier CSV Qonto
(:func:`argos_ops.poles.finance.expenses.audit`, met à jour le journal vendors) et
écrit un fait ``kind="expense_anomaly"`` par anomalie (``important`` pour les
outliers / doublons — fraude ou double prélèvement potentiel ; ``new_vendor`` reste
informatif).
"""

from __future__ import annotations

from pathlib import Path

from argos_ops.poles.base import BaseScript, ScriptResult
from argos_ops.poles.config import POLES_DIR
from argos_ops.poles.finance import expenses


class ExpenseAuditorScript(BaseScript):
    """Anomalies de dépenses (``kind="expense_anomaly"``)."""

    pole = "finance"
    name = "expense_auditor"

    def __init__(self, *, poles_root: Path = POLES_DIR) -> None:
        super().__init__(poles_root=poles_root)

    async def run(self) -> ScriptResult:
        report = expenses.audit(poles_root=self.poles_root, update_history=True)
        written = []
        for a in report.anomalies:
            important = a.kind in ("amount_outlier", "duplicate")
            written.append(
                await self.write_memory(
                    f"Anomalie {a.kind} — {a.expense.vendor} {a.expense.amount_eur} € "
                    f"le {a.expense.settled_on} : {a.reason}",
                    kind="expense_anomaly",
                    tags=("expense", a.kind) + (("critical",) if important else ()),
                    important=important,
                    source=(report.source_csv.name if report.source_csv else None),
                )
            )
        return ScriptResult(status="success", summary=report.summary, written=written)


__all__ = ["ExpenseAuditorScript"]
