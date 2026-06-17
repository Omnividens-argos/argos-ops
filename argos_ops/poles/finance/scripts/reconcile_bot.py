"""``ReconcileBotScript`` — rapprochement bancaire (Finance, archi v2, S5).

Bras déterministe : rapproche les payouts Stripe déclarés avec les crédits du
dernier export Qonto (:func:`argos_ops.poles.finance.reconcile.reconcile_report`)
et écrit un fait ``kind="reconcile"`` (``important`` s'il reste des orphelins —
bug d'export ou fraude à investiguer).
"""

from __future__ import annotations

from pathlib import Path

from argos_ops.poles.base import BaseScript, ScriptResult
from argos_ops.poles.config import POLES_DIR
from argos_ops.poles.finance import reconcile


class ReconcileBotScript(BaseScript):
    """Rapprochement payouts ↔ crédits Qonto (``kind="reconcile"``)."""

    pole = "finance"
    name = "reconcile_bot"

    def __init__(self, *, poles_root: Path = POLES_DIR) -> None:
        super().__init__(poles_root=poles_root)

    async def run(self) -> ScriptResult:
        report = reconcile.reconcile_report(poles_root=self.poles_root)
        n_orphans = len(report.orphan_payouts) + len(report.orphan_credits)
        important = n_orphans > 0
        record = await self.write_memory(
            f"Rapprochement : {report.summary}",
            kind="reconcile",
            tags=("reconcile",) + (("critical",) if report.orphan_payouts else ()),
            important=important,
        )
        return ScriptResult(
            status="success",
            summary=f"{report.summary}",
            written=[record],
        )


__all__ = ["ReconcileBotScript"]
