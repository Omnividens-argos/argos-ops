"""``BloctelGuardScript`` — garde-fou conformité Bloctel (Vente, archi v2, S4).

Bras déterministe **et garde-fou central** du pôle (analogue du breaker
``ad_spend_runaway`` de Pub) : croise les téléphones leads
(``compliance/lead_phones.csv``) avec la dernière liste mensuelle d'opposition
Bloctel (``compliance/bloctel/bloctel_YYYY-MM.txt``) via
:func:`argos_ops.poles.vente.outreach.build_bloctel_report`.

Écrit un fait ``kind="compliance_alert"`` **important** si la conformité n'est pas
garantie (téléphone opposé trouvé, ou liste périmée alors qu'il y a des numéros à
vérifier) — sinon un fait ``kind="compliance"`` neutre. Le ``VenteAgent`` gèle
alors tout l'outbound (« Python tranche »). Pas de Discord, pas de LLM (D-017).
"""

from __future__ import annotations

from pathlib import Path

from argos_ops.poles.base import BaseScript, ScriptResult
from argos_ops.poles.config import POLES_DIR
from argos_ops.poles.vente import outreach


class BloctelGuardScript(BaseScript):
    """Vérifie la conformité Bloctel et arme l'alerte (``kind="compliance_alert"``)."""

    pole = "vente"
    name = "bloctel_guard"

    def __init__(self, *, poles_root: Path = POLES_DIR) -> None:
        super().__init__(poles_root=poles_root)

    async def run(self) -> ScriptResult:
        report = outreach.build_bloctel_report(poles_root=self.poles_root)

        if report.should_alert:
            record = await self.write_memory(
                f"Conformité Bloctel : {report.summary}",
                kind="compliance_alert",
                tags=("bloctel", "critical"),
                important=True,
            )
        else:
            record = await self.write_memory(
                f"Conformité Bloctel OK : {report.summary}",
                kind="compliance",
                tags=("bloctel",),
            )

        return ScriptResult(
            status="success",
            summary=report.summary
            + (f" — {len(report.matches)} match(s)" if report.matches else ""),
            written=[record],
        )


__all__ = ["BloctelGuardScript"]
