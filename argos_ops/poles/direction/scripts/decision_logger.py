"""``DecisionLoggerScript`` — recensement du journal des décisions (Direction, S6).

Bras déterministe : relit le journal local des décisions
(:func:`argos_ops.poles.direction.decisions.load_decisions`) et écrit un fait
``kind="decision"`` ``important`` par décision (connaissance de gouvernance
protégée du nettoyage). Skip silencieux si le journal est vide. Idempotent.
"""

from __future__ import annotations

from argos_ops.poles.base import BaseScript, ScriptResult
from argos_ops.poles.direction import decisions
from argos_ops.poles.memory import MemoryRecord


class DecisionLoggerScript(BaseScript):
    """Décisions structurantes recensées (``kind="decision"``, important)."""

    pole = "direction"
    name = "decision_logger"

    async def run(self) -> ScriptResult:
        entries = decisions.load_decisions(poles_root=self.poles_root)
        if not entries:
            return ScriptResult(status="success", summary="journal vide — skip", written=[])
        written: list[MemoryRecord] = []
        for entry in entries:
            body = f"Décision {entry.decision_id} — {entry.title} : {entry.decision}"
            record = await self.write_memory(
                body[:400],
                kind="decision",
                tags=("decision", (entry.partie or "direction").lower()),
                important=True,
            )
            written.append(record)
        return ScriptResult(
            status="success", summary=f"{len(entries)} décision(s) recensée(s)", written=written
        )


__all__ = ["DecisionLoggerScript"]
