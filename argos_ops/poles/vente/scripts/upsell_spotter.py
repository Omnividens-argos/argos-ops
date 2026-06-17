"""``UpsellSpotterScript`` — comptes mûrs pour upsell (Vente, archi v2, S4).

Bras déterministe : charge ``data/poles/vente/cs/customers.yaml`` et repère les
comptes saturés (usage ≥ 80 % du quota plan) via
:func:`argos_ops.poles.vente.accounts.detect_upsells`. Écrit un fait
``kind="upsell"`` par candidat (non important — opportunité, pas urgence).
"""

from __future__ import annotations

from pathlib import Path

from argos_ops.poles.base import BaseScript, ScriptResult
from argos_ops.poles.config import POLES_DIR
from argos_ops.poles.vente import accounts


class UpsellSpotterScript(BaseScript):
    """Mémorise les candidats upsell (``kind="upsell"``)."""

    pole = "vente"
    name = "upsell_spotter"

    def __init__(self, *, poles_root: Path = POLES_DIR) -> None:
        super().__init__(poles_root=poles_root)

    async def run(self) -> ScriptResult:
        customers = accounts.load_accounts(poles_root=self.poles_root)
        candidates = accounts.detect_upsells(customers)
        if not candidates:
            return ScriptResult(
                status="success",
                summary=f"{len(customers)} compte(s) analysé(s) — aucun candidat upsell.",
                written=[],
            )

        written = []
        for c in candidates:
            record = await self.write_memory(
                f"Upsell {c.customer_id} — usage {c.usage_ratio:.0%}, "
                f"proposer {c.suggested_plan.value} : {c.reason}",
                kind="upsell",
                tags=(c.suggested_plan.value,),
                source=c.customer_id,
            )
            written.append(record)

        return ScriptResult(
            status="success",
            summary=f"{len(candidates)} candidat(s) upsell détecté(s)",
            written=written,
        )


__all__ = ["UpsellSpotterScript"]
