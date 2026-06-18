"""``CapabilityRouterScript`` — audit du câblage inter-pôles (archi v2, S7).

Bras déterministe read-only : lance :func:`~argos_ops.poles.memoire.wiring.audit_wiring`
(le « qui lit qui » des ``reads_cross_pole``) et écrit un fait de synthèse —
``important`` si des **warnings** (orphelin / producteur non lu) existent, pour
que l'anomalie de câblage survive au nettoyage. Ne route rien (le routage se fait
quand chaque agent lit sa mémoire cross-pôle) : il **surveille la cohérence**.
"""

from __future__ import annotations

from argos_ops.poles.base import BaseScript, ScriptResult
from argos_ops.poles.memoire import wiring


class CapabilityRouterScript(BaseScript):
    """Audite ``reads_cross_pole`` de toute la flotte → fait ``wiring-audit``."""

    pole = "memoire"
    name = "capability_router"

    async def run(self) -> ScriptResult:
        audit = await wiring.audit_wiring(poles_root=self.poles_root)
        record = await self.write_memory(
            audit.summary,
            kind="wiring-audit",
            tags=("wiring", "audit"),
            important=audit.should_alert,
        )
        return ScriptResult(status="success", summary=audit.summary, written=[record])


__all__ = ["CapabilityRouterScript"]
