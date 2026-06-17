"""``ContractDeadlineScript`` — contrats clients (Finance, archi v2, S5).

Bras déterministe : calcule les prochaines échéances de renouvellement des
contrats clients (:func:`argos_ops.poles.finance.contracts.client_report`) et écrit
un fait ``kind="client_contract"`` par contrat hors ``ok`` (``important`` si urgent
/ expiré — préparer l'upsell ou la résiliation avant tacite reconduction).
"""

from __future__ import annotations

from pathlib import Path

from argos_ops.poles.base import BaseScript, ScriptResult
from argos_ops.poles.config import POLES_DIR
from argos_ops.poles.finance import contracts


class ContractDeadlineScript(BaseScript):
    """Échéances contrats clients (``kind="client_contract"``)."""

    pole = "finance"
    name = "contract_deadline"

    def __init__(self, *, poles_root: Path = POLES_DIR) -> None:
        super().__init__(poles_root=poles_root)

    async def run(self) -> ScriptResult:
        renewals = contracts.client_renewals(poles_root=self.poles_root)
        written = []
        for r in renewals:
            if r.status == "ok":
                continue
            important = r.status in ("urgent", "expired")
            written.append(
                await self.write_memory(
                    f"Contrat client {r.client} — renouvellement {r.next_renewal} "
                    f"(J{r.days_left:+d}, {r.status})",
                    kind="client_contract",
                    tags=("contract", r.status) + (("critical",) if important else ()),
                    important=important,
                    source=r.client,
                )
            )
        report = contracts.client_report(poles_root=self.poles_root)
        return ScriptResult(status="success", summary=report.summary, written=written)


__all__ = ["ContractDeadlineScript"]
