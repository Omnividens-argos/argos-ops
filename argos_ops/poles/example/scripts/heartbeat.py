"""``HeartbeatScript`` — bras déterministe de démonstration (pôle ``_example``).

Gabarit minimal d'un :class:`~argos_ops.poles.base.BaseScript` : il calcule un
fait trivial (un battement de cœur horodaté) et l'écrit dans sa mémoire. Aucune
I/O réseau, aucune DB — 100 % déterministe et idempotent (le corps inclut une
clé stable, donc relancer n'empile pas les faits).
"""

from __future__ import annotations

from argos_ops.poles.base import BaseScript, ScriptResult


class HeartbeatScript(BaseScript):
    """Écrit un unique fait ``heartbeat`` dans la mémoire du pôle ``_example``."""

    pole = "_example"
    name = "heartbeat"

    async def run(self) -> ScriptResult:
        record = await self.write_memory(
            "Heartbeat — fait déterministe de démonstration écrit par un script.",
            kind="heartbeat",
            tags=("demo", "socle"),
            important=False,
        )
        return ScriptResult(
            status="success",
            summary="1 fait heartbeat écrit en mémoire.",
            written=[record],
        )
