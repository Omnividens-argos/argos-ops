"""``LeadEnricherScript`` — enrichit les leads du CSV inbox (Vente, archi v2, S4).

Bras déterministe : lit ``outbound/inbox/leads.csv``, enrichit chaque lead
(email probable / persona ICP / score BANT) via
:func:`argos_ops.poles.vente.outreach.enrich_and_write` (heuristiques offline,
port du skill ``lead-enricher``) et écrit ``outbound/enriched/<slug>.md``. Écrit un
fait ``kind="lead"`` par lead, **important** si éligible (email pro identifiable +
RGPD + BANT ≥ 40) — c'est ce que le ``VenteAgent`` transforme en action « lancer une
séquence outbound » (gelée si Bloctel l'exige).

Idempotent : ``enrich_and_write`` ré-écrit le même contenu pour un même lead. Pas
de réseau, pas de LLM (D-017).
"""

from __future__ import annotations

from pathlib import Path

from argos_ops.poles.base import BaseScript, ScriptResult
from argos_ops.poles.config import POLES_DIR
from argos_ops.poles.vente import outreach


class LeadEnricherScript(BaseScript):
    """Enrichit l'inbox CSV et mémorise les leads (``kind="lead"``)."""

    pole = "vente"
    name = "lead_enricher"

    def __init__(self, *, poles_root: Path = POLES_DIR) -> None:
        super().__init__(poles_root=poles_root)

    async def run(self) -> ScriptResult:
        leads = outreach.load_leads(poles_root=self.poles_root)
        if not leads:
            return ScriptResult(
                status="success",
                summary="Aucun lead (data/poles/vente/outbound/inbox/leads.csv) — rien à enrichir.",
                written=[],
            )

        written = []
        qualified = 0
        eligible = 0
        for lead in leads:
            enriched = outreach.enrich_and_write(lead, poles_root=self.poles_root)
            if enriched.qualified:
                qualified += 1
            if enriched.eligible:
                eligible += 1
            tags = (
                enriched.persona,
                "qualified" if enriched.qualified else "unqualified",
                "eligible" if enriched.eligible else "ineligible",
            )
            record = await self.write_memory(
                f"Lead {enriched.full_name} ({enriched.domain}) — persona {enriched.persona}, "
                f"BANT {enriched.bant_total}/100 — {enriched.eligibility_reason}",
                kind="lead",
                tags=tags,
                # important ⇒ l'agent en fait une action outbound : on ne flague que
                # les leads RÉELLEMENT contactables (email + RGPD + BANT), pas juste
                # qualifiés. La per-lead eligibility borne l'action ; Bloctel gèle au global.
                important=enriched.eligible,
                source=enriched.domain,
            )
            written.append(record)

        return ScriptResult(
            status="success",
            summary=(
                f"{len(leads)} lead(s) enrichi(s) — {qualified} qualifié(s), "
                f"{eligible} éligible(s) outbound"
            ),
            written=written,
        )


__all__ = ["LeadEnricherScript"]
