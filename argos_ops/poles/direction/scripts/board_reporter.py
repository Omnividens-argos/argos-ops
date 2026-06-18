"""``BoardReporterScript`` — board pack mensuel (Direction, S6).

Bras déterministe : assemble les KPIs board pack (finance depuis le snapshot
fichier + opérations depuis la vue d'ensemble flotte), génère le markdown
pandoc-ready (:func:`argos_ops.poles.direction.docs.generate_board`) et écrit un
fait ``kind="board"`` ``important`` (livrable investisseurs). Local-first.
"""

from __future__ import annotations

from argos_ops.poles.base import BaseScript, ScriptResult
from argos_ops.poles.direction import board, docs
from argos_ops.poles.direction.fleet import build_fleet_snapshot


class BoardReporterScript(BaseScript):
    """Board pack mensuel (``kind="board"``)."""

    pole = "direction"
    name = "board_reporter"

    async def run(self) -> ScriptResult:
        snapshot = await build_fleet_snapshot(poles_root=self.poles_root)
        metrics = board.build_metrics(snapshot, poles_root=self.poles_root)
        path = docs.generate_board(snapshot, poles_root=self.poles_root)
        runway = f"{metrics.runway_months:.1f}" if metrics.runway_months is not None else "∞"
        record = await self.write_memory(
            f"Board pack {metrics.period} généré : MRR {metrics.mrr_eur:.0f} €, "
            f"runway {runway} mois, {metrics.breakers_tripped} pôle(s) en alerte.",
            kind="board",
            tags=("board", metrics.period),
            important=True,
            source=path.name,
        )
        return ScriptResult(
            status="success", summary=f"board pack {metrics.period}", written=[record]
        )


__all__ = ["BoardReporterScript"]
