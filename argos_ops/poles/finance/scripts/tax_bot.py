"""``TaxBotScript`` — TVA CA3 + IS (Finance, archi v2, S5).

Bras déterministe : calcule la CA3 du mois (CA HT = MRR proxy), génère le doc
``docs/ca3_<YYYY-MM>.md`` (+ PDF si pandoc) et écrit un fait ``kind="fiscal"``
**important** (document fiscal — protégé du nettoyage). Aucun dépôt DGFiP : draft
à auditer par le fondateur avant le 19 du mois M+1.
"""

from __future__ import annotations

from pathlib import Path

from argos_ops.poles.base import BaseScript, ScriptResult
from argos_ops.poles.config import POLES_DIR
from argos_ops.poles.finance import docs, taxes


class TaxBotScript(BaseScript):
    """TVA CA3 mensuelle (``kind="fiscal"``, important)."""

    pole = "finance"
    name = "tax_bot"

    def __init__(self, *, poles_root: Path = POLES_DIR) -> None:
        super().__init__(poles_root=poles_root)

    async def run(self) -> ScriptResult:
        ca3 = taxes.current_ca3(poles_root=self.poles_root)
        docs.generate_ca3(poles_root=self.poles_root, period_month=ca3.period_month)
        record = await self.write_memory(
            f"Déclaration TVA CA3 {ca3.period_month} : base HT {ca3.ca_ht_eur} €, "
            f"TVA collectée {ca3.tva_collected_eur} €, nette due {ca3.tva_net_due_eur} €",
            kind="fiscal",
            tags=("fiscal", "tva"),
            important=True,
            source=ca3.period_month,
        )
        return ScriptResult(status="success", summary=ca3.summary(), written=[record])


__all__ = ["TaxBotScript"]
