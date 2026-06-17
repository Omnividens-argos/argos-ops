"""``IncidentLoggerScript`` — registre des incidents (Finance, archi v2, S5).

Bras déterministe : recense les post-mortems d'incidents sécurité
(:func:`argos_ops.poles.finance.incidents.list_incidents`) et écrit un fait
``kind="incident"`` **important** (document légal — RGPD art. 33 notification CNIL)
par incident encore ``open``. Le scaffold d'un nouvel incident reste une action
interactive (cockpit / ``/log-incident``), pas un effet de bord de ce script.
"""

from __future__ import annotations

from pathlib import Path

from argos_ops.poles.base import BaseScript, ScriptResult
from argos_ops.poles.config import POLES_DIR
from argos_ops.poles.finance import incidents


class IncidentLoggerScript(BaseScript):
    """Incidents ouverts (``kind="incident"``, important)."""

    pole = "finance"
    name = "incident_logger"

    def __init__(self, *, poles_root: Path = POLES_DIR) -> None:
        super().__init__(poles_root=poles_root)

    async def run(self) -> ScriptResult:
        items = incidents.list_incidents(poles_root=self.poles_root)
        open_items = [i for i in items if i.status == "open"]
        written = []
        for inc in open_items:
            written.append(
                await self.write_memory(
                    f"Incident {inc.severity} {inc.category} — {inc.title} ({inc.status})",
                    kind="incident",
                    tags=("incident", inc.severity),
                    important=True,
                    source=inc.slug,
                )
            )
        return ScriptResult(
            status="success",
            summary=f"{len(open_items)} incident(s) ouvert(s) sur {len(items)} archivé(s)",
            written=written,
        )


__all__ = ["IncidentLoggerScript"]
