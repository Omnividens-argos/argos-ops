"""``MeetingBookerScript`` — drafte les confirmations de RDV (Vente, archi v2, S4).

Bras déterministe : pour chaque demande de RDV ``pending`` de
``data/poles/vente/meetings/requests.yaml``, drafte un email de confirmation + une
invitation iCalendar (:func:`argos_ops.poles.vente.meetings.book_meeting`) et écrit
un fait ``kind="meeting"`` que le ``VenteAgent`` transforme en action « envoyer la
confirmation ». Idempotent : une demande déjà ``drafted`` n'est pas re-traitée.

Humain-in-the-loop : on drafte, le fondateur envoie via ``zimbra-ops``. Pas de
Discord, pas de LLM (D-017).
"""

from __future__ import annotations

from pathlib import Path

from argos_ops.poles.base import BaseScript, ScriptResult
from argos_ops.poles.config import POLES_DIR
from argos_ops.poles.vente import meetings


class MeetingBookerScript(BaseScript):
    """Drafte les RDV pending (iCal + email) et les mémorise (``kind="meeting"``)."""

    pole = "vente"
    name = "meeting_booker"

    def __init__(self, *, poles_root: Path = POLES_DIR) -> None:
        super().__init__(poles_root=poles_root)

    async def run(self) -> ScriptResult:
        requests = meetings.load_requests(poles_root=self.poles_root)
        todo = meetings.pending(requests)
        if not todo:
            return ScriptResult(
                status="success",
                summary=f"{len(requests)} demande(s) de RDV, aucune en attente — rien à drafter.",
                written=[],
            )

        written = []
        for req in todo:
            draft = meetings.book_meeting(req.request_id, poles_root=self.poles_root)
            if draft is None:
                continue
            record = await self.write_memory(
                f"RDV drafté pour {req.attendee_name or req.attendee_email} "
                f"({req.company or '?'}) le {req.starts_at.date().isoformat()} — iCal prêt",
                kind="meeting",
                tags=("drafted",),
                source=req.attendee_email,
            )
            written.append(record)

        return ScriptResult(
            status="success",
            summary=f"{len(written)} confirmation(s) de RDV draftée(s) (iCal + email)",
            written=written,
        )


__all__ = ["MeetingBookerScript"]
