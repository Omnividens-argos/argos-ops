"""``ProposalBotScript`` — génère les devis (Vente, archi v2, S4).

Bras déterministe : pour chaque deal ayant un
``data/poles/vente/proposals/<deal_id>/context.yaml``, rend ``proposal.md``
(:func:`argos_ops.poles.vente.proposals.render_proposal_file`, idempotent) et écrit
un fait ``kind="proposal"``. Le PDF est tenté via pandoc s'il est dispo (sinon
Markdown seul — D-009). Humain-in-the-loop : le fondateur relit, envoie, puis
marque ``proposal_status: sent`` pour débloquer le contrat.
"""

from __future__ import annotations

from pathlib import Path

from argos_ops.poles.base import BaseScript, ScriptResult
from argos_ops.poles.config import POLES_DIR
from argos_ops.poles.vente import proposals


class ProposalBotScript(BaseScript):
    """Rend les devis et les mémorise (``kind="proposal"``)."""

    pole = "vente"
    name = "proposal_bot"

    def __init__(self, *, poles_root: Path = POLES_DIR) -> None:
        super().__init__(poles_root=poles_root)

    async def run(self) -> ScriptResult:
        entries = proposals.load_entries(poles_root=self.poles_root)
        if not entries:
            return ScriptResult(
                status="success",
                summary="Aucun deal devis (data/poles/vente/proposals/<deal>/context.yaml).",
                written=[],
            )

        written = []
        rendered = 0
        for entry in entries:
            path = proposals.render_proposal_file(entry.deal_id, poles_root=self.poles_root)
            if path is None:
                continue
            rendered += 1
            record = await self.write_memory(
                f"Devis {entry.deal_id} ({entry.company}) — {entry.plan} "
                f"{entry.monthly_price_eur}€/mois",
                kind="proposal",
                tags=(entry.deal_id, entry.proposal_status),
                source=entry.deal_id,
            )
            written.append(record)

        return ScriptResult(
            status="success",
            summary=f"{rendered} devis rendu(s)/à jour sur {len(entries)} deal(s)",
            written=written,
        )


__all__ = ["ProposalBotScript"]
