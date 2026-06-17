"""``ProspectMinerScript`` — alimente le CSV de leads (Vente, archi v2, S4).

Bras déterministe : lit ``data/poles/vente/outbound/sources.yaml`` (entrées
``manual:`` saisies par le fondateur — recommandations, annonces repérées à la
main) et **append** les nouveaux prospects ICP à ``outbound/inbox/leads.csv`` via
:func:`argos_ops.poles.vente.outreach.append_leads` (dédup sur
``(full_name, domain)``). Écrit un fait ``kind="prospect"`` par prospect ajouté.

Politique D-016 / D-017 : aucun scraping LinkedIn, aucune API payante, aucun
réseau ici — uniquement des sources manuelles fichier (le fetch RSS auth-free
est hors périmètre S4, branchable plus tard). Idempotent : ré-exécuter ne
duplique pas les leads déjà présents.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from argos_ops.outbound.models import LeadInput
from argos_ops.poles.base import BaseScript, ScriptResult
from argos_ops.poles.config import POLES_DIR
from argos_ops.poles.vente import outreach


class ProspectMinerScript(BaseScript):
    """Append des prospects manuels au CSV inbox (``kind="prospect"``)."""

    pole = "vente"
    name = "prospect_miner"

    def __init__(self, *, poles_root: Path = POLES_DIR) -> None:
        super().__init__(poles_root=poles_root)

    def _sources_path(self) -> Path:
        return self.poles_root / "vente" / "outbound" / "sources.yaml"

    async def run(self) -> ScriptResult:
        sources = self._sources_path()
        if not sources.exists():
            return ScriptResult(
                status="success",
                summary="Aucune source prospects (data/poles/vente/outbound/sources.yaml).",
                written=[],
            )
        raw = yaml.safe_load(sources.read_text(encoding="utf-8")) or {}
        manual = raw.get("manual", []) if isinstance(raw, dict) else []

        candidates: list[LeadInput] = []
        for entry in manual:
            if not isinstance(entry, dict):
                continue
            full_name = str(entry.get("full_name") or "").strip()
            domain = str(entry.get("domain") or "").strip().lower()
            if not full_name or not domain:
                continue
            candidates.append(
                LeadInput(
                    full_name=full_name,
                    domain=domain,
                    title_hint=str(entry.get("title_hint") or "").strip() or None,
                    linkedin_url=str(entry.get("linkedin_url") or "").strip() or None,
                )
            )

        added, skipped = outreach.append_leads(candidates, poles_root=self.poles_root)

        written = []
        for lead in added:
            record = await self.write_memory(
                f"Nouveau prospect ICP : {lead.full_name} ({lead.domain})"
                + (f" — {lead.title_hint}" if lead.title_hint else ""),
                kind="prospect",
                tags=("manual",),
                source=lead.domain,
            )
            written.append(record)

        return ScriptResult(
            status="success",
            summary=f"{len(added)} prospect(s) ajouté(s), {skipped} ignoré(s) (doublon/invalide)",
            written=written,
        )


__all__ = ["ProspectMinerScript"]
