"""``OutboundSenderScript`` — envoi des séquences outbound (Vente, archi v2, S4).

Bras déterministe en **mode shadow** (D-026 / D-017) : scanne les séquences
``outbound/sequences/<slug>/``, détermine le mode (``frozen`` si la conformité
Bloctel gèle l'outbound, sinon ``shadow``) et **journalise** les touches dont la
date est échue et le corps drafté — **aucun envoi SMTP réel** tant que le live
mode (P13.B) n'est pas activé. Écrit un fait ``kind="outbound"``.

Garde-fou : si :func:`argos_ops.poles.vente.outreach.outbound_frozen` est armé,
aucune touche n'est journalisée comme « prête à partir » (Python tranche).
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from argos_ops.poles.base import BaseScript, ScriptResult
from argos_ops.poles.config import POLES_DIR
from argos_ops.poles.vente import outreach


class OutboundSenderScript(BaseScript):
    """Scanne les séquences et journalise les envois (shadow) — ``kind="outbound"``."""

    pole = "vente"
    name = "outbound_sender"

    def __init__(self, *, poles_root: Path = POLES_DIR) -> None:
        super().__init__(poles_root=poles_root)

    async def run(self) -> ScriptResult:
        sequences = outreach.load_sequences(poles_root=self.poles_root)
        if not sequences:
            return ScriptResult(
                status="success",
                summary="Aucune séquence outbound scaffoldée — rien à envoyer.",
                written=[],
            )

        frozen = outreach.outbound_frozen(poles_root=self.poles_root)
        today = datetime.now(UTC).date()

        if frozen:
            record = await self.write_memory(
                f"Outbound GELÉ (conformité Bloctel) — {len(sequences)} séquence(s) en attente, "
                "aucune touche envoyée.",
                kind="outbound",
                tags=("frozen",),
            )
            return ScriptResult(
                status="success",
                summary=f"Outbound gelé (Bloctel) — {len(sequences)} séquence(s) suspendue(s)",
                written=[record],
            )

        ready = 0
        for seq in sequences:
            for touch in seq.touches:
                if touch.scheduled_date <= today and touch.status == "drafted" and touch.body:
                    ready += 1

        record = await self.write_memory(
            f"Outbound shadow : {len(sequences)} séquence(s) scannée(s), "
            f"{ready} touche(s) prête(s) (aucun envoi réel — shadow).",
            kind="outbound",
            tags=("shadow",),
        )
        return ScriptResult(
            status="success",
            summary=f"{len(sequences)} séquence(s), {ready} touche(s) prête(s) — mode shadow",
            written=[record],
        )


__all__ = ["OutboundSenderScript"]
