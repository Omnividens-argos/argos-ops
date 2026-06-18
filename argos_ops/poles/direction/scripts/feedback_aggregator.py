"""``FeedbackAggregatorScript`` — agrégation du feedback produit (Direction, S6).

Bras déterministe : agrège le feedback par thème
(:func:`argos_ops.poles.direction.feedback.build_report`) et écrit un fait
``kind="feedback"`` par thème — ``important`` (tag ``recurring``) si le thème est
**récurrent** (≥ seuil de mentions). Skip silencieux si aucun feedback. Local-first.
"""

from __future__ import annotations

from argos_ops.poles.base import BaseScript, ScriptResult
from argos_ops.poles.direction import feedback
from argos_ops.poles.memory import MemoryRecord


class FeedbackAggregatorScript(BaseScript):
    """Demandes produit agrégées (``kind="feedback"``)."""

    pole = "direction"
    name = "feedback_aggregator"

    async def run(self) -> ScriptResult:
        report = feedback.build_report(poles_root=self.poles_root)
        if not report.themes:
            return ScriptResult(status="success", summary="aucun feedback — skip", written=[])
        recurring = {t.topic for t in feedback.recurring_themes(poles_root=self.poles_root)}
        written: list[MemoryRecord] = []
        for theme in report.themes:
            is_recurring = theme.topic in recurring
            clients = ", ".join(theme.customers[:3]) or "clients non identifiés"
            record = await self.write_memory(
                f"Demande produit : « {theme.topic} » ({theme.count} mention(s) — {clients})",
                kind="feedback",
                tags=("feedback",) + (("recurring",) if is_recurring else ()),
                important=is_recurring,
            )
            written.append(record)
        return ScriptResult(status="success", summary=report.summary(), written=written)


__all__ = ["FeedbackAggregatorScript"]
