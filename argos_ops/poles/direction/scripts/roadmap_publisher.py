"""``RoadmapPublisherScript`` — état de la roadmap publique (Direction, S6).

Bras déterministe : lit l'Annexe D locale
(:func:`argos_ops.poles.direction.roadmap.build_roadmap`) et écrit un fait
``kind="roadmap"`` (artefact **public** — publication soumise au garde-fou release).
Skip silencieux si l'Annexe D est vide. Local-first.
"""

from __future__ import annotations

from argos_ops.poles.base import BaseScript, ScriptResult
from argos_ops.poles.direction import roadmap


class RoadmapPublisherScript(BaseScript):
    """État roadmap publique (``kind="roadmap"``)."""

    pole = "direction"
    name = "roadmap_publisher"

    async def run(self) -> ScriptResult:
        view = roadmap.build_roadmap(poles_root=self.poles_root)
        if not view.entries_total:
            return ScriptResult(status="success", summary="Annexe D vide — skip", written=[])
        record = await self.write_memory(
            f"Roadmap publique : {view.done} livré(s) / {view.partial} en cours / "
            f"{view.roadmap} à venir sur {view.services} service(s) — prête à publier.",
            kind="roadmap",
            tags=("publish", "roadmap"),
        )
        return ScriptResult(
            status="success", summary=f"{view.entries_total} entrée(s)", written=[record]
        )


__all__ = ["RoadmapPublisherScript"]
