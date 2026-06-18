"""``DigestBuilderScript`` — digest quotidien de la flotte (Direction, S6).

Bras déterministe : le « morning digest » de la flotte. Lit la vue d'ensemble
(:func:`argos_ops.poles.direction.fleet.build_fleet_snapshot`) et écrit un fait
``kind="digest"`` (portée ``daily``). Local-first.
"""

from __future__ import annotations

from argos_ops.poles.base import BaseScript, ScriptResult
from argos_ops.poles.direction import digest
from argos_ops.poles.direction.fleet import build_fleet_snapshot


class DigestBuilderScript(BaseScript):
    """Digest quotidien flotte (``kind="digest"``)."""

    pole = "direction"
    name = "digest_builder"

    async def run(self) -> ScriptResult:
        snapshot = await build_fleet_snapshot(poles_root=self.poles_root)
        report = digest.build_digest(snapshot, scope="daily")
        record = await self.write_memory(report.headline, kind="digest", tags=("daily",))
        return ScriptResult(status="success", summary=report.summary, written=[record])


__all__ = ["DigestBuilderScript"]
