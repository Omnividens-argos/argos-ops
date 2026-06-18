"""``ContractGeneratorScript`` — génère les contrats (Vente, archi v2, S4).

Bras déterministe : pour chaque deal dont le devis est marqué ``sent``, rend
``contract.md`` (:func:`argos_ops.poles.vente.proposals.render_contract_file`,
idempotent) et écrit un fait ``kind="contract"`` **important** (étape engageante).
Un deal dont le devis n'est pas encore ``sent`` est ignoré (le contrat ne se génère
jamais avant l'acceptation du devis). PDF tenté via pandoc si dispo (D-009).
"""

from __future__ import annotations

from pathlib import Path

from argos_ops.poles.base import BaseScript, ScriptResult
from argos_ops.poles.config import POLES_DIR
from argos_ops.poles.vente import proposals


class ContractGeneratorScript(BaseScript):
    """Rend les contrats des devis acceptés (``kind="contract"``)."""

    pole = "vente"
    name = "contract_generator"

    def __init__(self, *, poles_root: Path = POLES_DIR) -> None:
        super().__init__(poles_root=poles_root)

    async def run(self) -> ScriptResult:
        entries = proposals.load_entries(poles_root=self.poles_root)
        if not entries:
            return ScriptResult(
                status="success",
                summary="Aucun deal devis — aucun contrat à générer.",
                written=[],
            )

        written = []
        generated = 0
        waiting = 0
        for entry in entries:
            if entry.proposal_status != "sent":
                waiting += 1
                continue
            path = proposals.render_contract_file(entry.deal_id, poles_root=self.poles_root)
            if path is None:
                continue
            generated += 1
            record = await self.write_memory(
                f"Contrat {entry.deal_id} ({entry.company}) généré — devis accepté, "
                f"{entry.plan} {entry.monthly_price_eur}€/mois",
                kind="contract",
                tags=(entry.deal_id,),
                important=True,
                source=entry.deal_id,
            )
            written.append(record)

        return ScriptResult(
            status="success",
            summary=(
                f"{generated} contrat(s) généré(s), {waiting} deal(s) en attente "
                "(devis pas encore marqué sent)"
            ),
            written=written,
        )


__all__ = ["ContractGeneratorScript"]
