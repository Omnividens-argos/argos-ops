"""``StrategyBotScript`` — digest hebdomadaire de la flotte (Direction, S6).

Bras déterministe : lit la vue d'ensemble de toute la flotte
(:func:`argos_ops.poles.direction.fleet.build_fleet_snapshot`) et écrit un fait
``kind="strategy"`` résumant la semaine (chief of staff). Local-first : la source
est la mémoire des pôles (remplace les requêtes Postgres du legacy ``strategy_bot``).
"""

from __future__ import annotations

from argos_ops.poles.base import BaseScript, ScriptResult
from argos_ops.poles.direction import digest
from argos_ops.poles.direction.fleet import build_fleet_snapshot


class StrategyBotScript(BaseScript):
    """Digest hebdomadaire flotte (``kind="strategy"``)."""

    pole = "direction"
    name = "strategy_bot"

    async def run(self) -> ScriptResult:
        snapshot = await build_fleet_snapshot(poles_root=self.poles_root)
        report = digest.build_digest(snapshot, scope="weekly")
        record = await self.write_memory(report.headline, kind="strategy", tags=("weekly",))
        return ScriptResult(status="success", summary=report.summary, written=[record])


__all__ = ["StrategyBotScript"]
