"""``VendorContractWatcherScript`` — contrats fournisseurs (Finance, archi v2, S5).

Bras déterministe : calcule les échéances d'annulation des contrats fournisseurs
(:func:`argos_ops.poles.finance.contracts.vendor_report`) et écrit un fait
``kind="vendor_contract"`` par contrat hors ``ok`` (``important`` si urgent/raté —
tacite reconduction à ne pas manquer).
"""

from __future__ import annotations

from pathlib import Path

from argos_ops.poles.base import BaseScript, ScriptResult
from argos_ops.poles.config import POLES_DIR
from argos_ops.poles.finance import contracts


class VendorContractWatcherScript(BaseScript):
    """Échéances contrats fournisseurs (``kind="vendor_contract"``)."""

    pole = "finance"
    name = "vendor_contract_watcher"

    def __init__(self, *, poles_root: Path = POLES_DIR) -> None:
        super().__init__(poles_root=poles_root)

    async def run(self) -> ScriptResult:
        report = contracts.vendor_report(poles_root=self.poles_root)
        written = []
        for c in report.contracts:
            if c.status == "ok":
                continue
            important = c.status in ("urgent", "missed")
            written.append(
                await self.write_memory(
                    f"Contrat fournisseur {c.vendor} — annulation avant {c.deadline_date} "
                    f"(J{c.days_until_deadline:+d}, {c.status}) · {c.monthly_cost_eur} €/mois",
                    kind="vendor_contract",
                    tags=("contract", c.status) + (("critical",) if important else ()),
                    important=important,
                    source=c.vendor,
                )
            )
        return ScriptResult(status="success", summary=report.summary, written=written)


__all__ = ["VendorContractWatcherScript"]
