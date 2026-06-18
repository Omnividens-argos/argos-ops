"""``BugTriageScript`` — triage des bugs par sévérité (Direction, S6).

Bras déterministe : trie les issues du snapshot local
(:func:`argos_ops.poles.direction.bugs.triage`) et écrit un fait ``kind="bug"`` par
bug **P0** (``important`` + tag ``p0``) ou **P1** (tag ``p1``). Les P2 ne génèrent
pas de fait (bruit). Skip silencieux si aucune issue. Le nombre de P0 alimente le
garde-fou de publication. Local-first (pas de fetch GitHub ici).
"""

from __future__ import annotations

from argos_ops.poles.base import BaseScript, ScriptResult
from argos_ops.poles.direction import bugs
from argos_ops.poles.memory import MemoryRecord


class BugTriageScript(BaseScript):
    """Bugs P0/P1 triés (``kind="bug"``)."""

    pole = "direction"
    name = "bug_triage"

    async def run(self) -> ScriptResult:
        stats = bugs.triage(poles_root=self.poles_root)
        if not stats.issues_total:
            return ScriptResult(status="success", summary="aucune issue — skip", written=[])
        written: list[MemoryRecord] = []
        for issue in stats.triaged:
            if issue.severity == "P2":
                continue
            record = await self.write_memory(
                f"Bug #{issue.number} [{issue.severity}] : {issue.title}",
                kind="bug",
                tags=("bug", issue.severity.lower()),
                important=(issue.severity == "P0"),
            )
            written.append(record)
        return ScriptResult(status="success", summary=stats.summary(), written=written)


__all__ = ["BugTriageScript"]
