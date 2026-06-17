"""``FinanceBotScript`` — snapshot Stripe + dunning (Finance, archi v2, S5).

Bras déterministe : lit le snapshot de facturation
(:func:`argos_ops.poles.finance.billing.build_billing_snapshot`), écrit un fait
``kind="mrr"`` (MRR/ARR + impayés) et un fait ``kind="dunning"`` par facture
impayée classée J+3/J+7/J+15 (``important`` pour J+15). Mode shadow : aucun envoi
de relance ici (le drafting est humain-in-the-loop côté cockpit). Pas de LLM,
pas de Discord (D-017).
"""

from __future__ import annotations

from pathlib import Path

from argos_ops.poles.base import BaseScript, ScriptResult
from argos_ops.poles.config import POLES_DIR
from argos_ops.poles.finance import billing


class FinanceBotScript(BaseScript):
    """Photo MRR/ARR + classification dunning (``kind="mrr"`` / ``kind="dunning"``)."""

    pole = "finance"
    name = "finance_bot"

    def __init__(self, *, poles_root: Path = POLES_DIR) -> None:
        super().__init__(poles_root=poles_root)

    async def run(self) -> ScriptResult:
        snap = billing.build_billing_snapshot(poles_root=self.poles_root)
        written = [
            await self.write_memory(
                f"MRR {snap.mrr_eur} € · ARR {snap.arr_eur} € · "
                f"{snap.n_active_subs}/{snap.n_subs} subs actives · "
                f"{snap.n_open_invoices} facture(s) impayée(s) ({snap.open_amount_eur} €)",
                kind="mrr",
                tags=("stripe", "mrr"),
            )
        ]
        for d in snap.dunning:
            if d.level == "none":
                continue
            important = d.level == "J+15"
            who = d.customer_name or d.customer_id or "client inconnu"
            written.append(
                await self.write_memory(
                    f"Relance {d.level} — facture {d.invoice_id} ({who}) "
                    f"{d.amount_due_eur} € impayée",
                    kind="dunning",
                    tags=("dunning", d.level) + (("critical",) if important else ()),
                    important=important,
                    source=d.invoice_id,
                )
            )
        return ScriptResult(
            status="success",
            summary=f"MRR {snap.mrr_eur} € · {snap.n_dunning_due} relance(s) due(s)",
            written=written,
        )


__all__ = ["FinanceBotScript"]
