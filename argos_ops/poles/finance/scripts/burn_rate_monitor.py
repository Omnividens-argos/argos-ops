"""``BurnRateMonitorScript`` — burn & runway (Finance, archi v2, S5).

Bras déterministe : lit l'état trésorerie déclaré et calcule net burn + runway
(:func:`argos_ops.poles.finance.treasury.burn_report`). Écrit un fait
``kind="treasury"`` (``important`` si runway sous le seuil d'alerte / burn > cap).
Skip silencieux si la trésorerie n'est pas encore renseignée.
"""

from __future__ import annotations

from pathlib import Path

from argos_ops.poles.base import BaseScript, ScriptResult
from argos_ops.poles.config import POLES_DIR
from argos_ops.poles.finance import treasury


class BurnRateMonitorScript(BaseScript):
    """Net burn + runway (``kind="treasury"``)."""

    pole = "finance"
    name = "burn_rate_monitor"

    def __init__(self, *, poles_root: Path = POLES_DIR) -> None:
        super().__init__(poles_root=poles_root)

    async def run(self) -> ScriptResult:
        report = treasury.burn_report(poles_root=self.poles_root)
        if report.snapshot is None:
            return ScriptResult(
                status="success",
                summary="treasury/state.yaml absent — skip (trésorerie non renseignée)",
                written=[],
            )
        important = report.should_alert
        record = await self.write_memory(
            f"Trésorerie : {report.summary}",
            kind="treasury",
            tags=("treasury",) + (("critical",) if important else ()),
            important=important,
        )
        return ScriptResult(status="success", summary=report.summary, written=[record])


__all__ = ["BurnRateMonitorScript"]
