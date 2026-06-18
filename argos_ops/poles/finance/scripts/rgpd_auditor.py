"""``RGPDAuditorScript`` — registre RGPD (Finance, archi v2, S5).

Bras déterministe **et co-garde-fou conformité** : valide le registre RGPD
(:func:`argos_ops.poles.finance.compliance.load_rgpd_registry`) et écrit un fait
``kind="rgpd"`` **important** (document légal — protégé). Tag ``gap`` + ``critical``
si une fiche est non conforme / le registre absent : le ``FinanceAgent`` gèle alors
l'onboarding d'un nouveau traitement (« Python tranche »).
"""

from __future__ import annotations

from pathlib import Path

from argos_ops.poles.base import BaseScript, ScriptResult
from argos_ops.poles.config import POLES_DIR
from argos_ops.poles.finance import compliance


class RGPDAuditorScript(BaseScript):
    """Validation registre RGPD (``kind="rgpd"``, important)."""

    pole = "finance"
    name = "rgpd_auditor"

    def __init__(self, *, poles_root: Path = POLES_DIR) -> None:
        super().__init__(poles_root=poles_root)

    async def run(self) -> ScriptResult:
        report = compliance.load_rgpd_registry(poles_root=self.poles_root)
        tags = ("rgpd",) + (("gap", "critical") if report.should_alert else ())
        record = await self.write_memory(
            f"Registre RGPD : {report.summary}",
            kind="rgpd",
            tags=tags,
            important=True,
        )
        return ScriptResult(status="success", summary=report.summary, written=[record])


__all__ = ["RGPDAuditorScript"]
