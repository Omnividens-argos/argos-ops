"""``AIActComplianceScript`` — registre AI Act (Finance, archi v2, S5).

Bras déterministe **et co-garde-fou conformité** : valide la classification AI Act
des systèmes déclarés (:func:`argos_ops.poles.finance.compliance.load_ai_act_registry`)
et écrit un fait ``kind="ai_act"`` **important** (document légal — protégé). Tag
``prohibited`` + ``critical`` si un système est interdit (art. 5) — le
``FinanceAgent`` gèle alors l'onboarding ; tag ``unclassified`` si un système n'est
pas documenté.
"""

from __future__ import annotations

from pathlib import Path

from argos_ops.poles.base import BaseScript, ScriptResult
from argos_ops.poles.config import POLES_DIR
from argos_ops.poles.finance import compliance


class AIActComplianceScript(BaseScript):
    """Validation registre AI Act (``kind="ai_act"``, important)."""

    pole = "finance"
    name = "ai_act_compliance"

    def __init__(self, *, poles_root: Path = POLES_DIR) -> None:
        super().__init__(poles_root=poles_root)

    async def run(self) -> ScriptResult:
        report = compliance.load_ai_act_registry(poles_root=self.poles_root)
        tags: tuple[str, ...] = ("ai_act",)
        if report.prohibited:
            tags += ("prohibited", "critical")
        elif report.unclassified:
            tags += ("unclassified",)
        record = await self.write_memory(
            f"Registre AI Act : {report.summary}",
            kind="ai_act",
            tags=tags,
            important=True,
        )
        return ScriptResult(status="success", summary=report.summary, written=[record])


__all__ = ["AIActComplianceScript"]
