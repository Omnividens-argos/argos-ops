"""``OKRTrackerScript`` — suivi OKR vs prorata temporis (Direction, S6).

Bras déterministe : lit les OKR du trimestre courant
(:func:`argos_ops.poles.direction.okr.load_current`) et écrit un fait ``kind="okr"``
par key result **en retard** (``off_track`` → ``important`` + tag critique ;
``at_risk`` → tag d'alerte). Skip silencieux si aucun fichier OKR.
"""

from __future__ import annotations

from argos_ops.poles.base import BaseScript, ScriptResult
from argos_ops.poles.direction import okr
from argos_ops.poles.memory import MemoryRecord


class OKRTrackerScript(BaseScript):
    """Key results en retard (``kind="okr"``)."""

    pole = "direction"
    name = "okr_tracker"

    async def run(self) -> ScriptResult:
        report = okr.load_current(poles_root=self.poles_root)
        if report.quarter == "<missing>":
            return ScriptResult(status="success", summary="aucun fichier OKR — skip", written=[])
        written: list[MemoryRecord] = []
        for kr in report.key_results:
            if kr.status not in ("off_track", "at_risk"):
                continue
            record = await self.write_memory(
                f"OKR « {kr.name} » {kr.status} : {kr.actual:.0f}/{kr.target:.0f} {kr.unit} "
                f"({kr.progress_pct * 100:.0f}% vs {kr.expected_pct * 100:.0f}% attendu)",
                kind="okr",
                tags=("okr", kr.status),
                important=(kr.status == "off_track"),
            )
            written.append(record)
        return ScriptResult(status="success", summary=report.summary, written=written)


__all__ = ["OKRTrackerScript"]
