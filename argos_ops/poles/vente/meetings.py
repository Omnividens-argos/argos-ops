"""RDV du pôle Vente (archi v2, S4) — demandes → confirmation + invitation iCal.

Charge ``data/poles/vente/meetings/requests.yaml`` (saisi à la main ou via une
réponse inbox) et, pour chaque demande ``pending``, drafte un email de
confirmation + une invitation iCalendar RFC 5545 via
:func:`argos_ops.sales.ical.build_ical_invite` (stdlib, 0 dépendance — D-009).

Idempotent : un RDV déjà drafté n'est pas re-généré (statut ``drafted``). Mode
humain-in-the-loop : on drafte, le fondateur envoie via ``zimbra-ops``.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import yaml

from argos_ops.poles.config import POLES_DIR
from argos_ops.poles.vente.store import write_markdown
from argos_ops.sales.ical import build_ical_invite
from argos_ops.sales.models import MeetingRequest

VENTE_POLE = "vente"

ORGANIZER_EMAIL = "contact@omnividens.fr"
ORGANIZER_NAME = "Omnividens (Argos)"
_PENDING = "pending"


def requests_path(*, poles_root: Path = POLES_DIR) -> Path:
    return poles_root / VENTE_POLE / "meetings" / "requests.yaml"


def drafts_dir(*, poles_root: Path = POLES_DIR) -> Path:
    return poles_root / VENTE_POLE / "meetings" / "drafts"


def _as_dt(value: object) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    parsed = datetime.fromisoformat(str(value))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def load_requests(*, poles_root: Path = POLES_DIR) -> list[MeetingRequest]:
    """Charge les demandes de RDV. Absent ⇒ ``[]`` (best-effort)."""
    path = requests_path(poles_root=poles_root)
    if not path.exists():
        return []
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    entries = raw.get("requests", []) if isinstance(raw, dict) else []
    out: list[MeetingRequest] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        out.append(
            MeetingRequest(
                request_id=str(entry["request_id"]),
                attendee_email=str(entry["attendee_email"]),
                attendee_name=str(entry.get("attendee_name", "")),
                company=str(entry.get("company", "")),
                starts_at=_as_dt(entry["starts_at"]),
                duration_minutes=int(entry.get("duration_minutes", 30)),
                location=str(entry.get("location", MeetingRequest.location)),
                status=str(entry.get("status", _PENDING)),
            )
        )
    return out


def _save_requests(requests: list[MeetingRequest], *, poles_root: Path = POLES_DIR) -> None:
    payload = {
        "requests": [
            {
                "request_id": r.request_id,
                "attendee_email": r.attendee_email,
                "attendee_name": r.attendee_name,
                "company": r.company,
                "starts_at": r.starts_at.isoformat(),
                "duration_minutes": r.duration_minutes,
                "location": r.location,
                "status": r.status,
            }
            for r in requests
        ]
    }
    path = requests_path(poles_root=poles_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, allow_unicode=True, sort_keys=False), encoding="utf-8")


def _confirmation_body(request: MeetingRequest) -> str:
    when = request.starts_at.astimezone(UTC).strftime("%Y-%m-%d %H:%M UTC")
    return (
        f"Bonjour {request.attendee_name or ''},\n\n"
        f"Je confirme notre rendez-vous le {when} "
        f"({request.duration_minutes} min).\n"
        f"Lieu : {request.location}\n\n"
        "L'invitation iCalendar est en pièce jointe (invitation.ics). "
        "Réponds si le créneau ne convient pas, je proposerai une alternative.\n\n"
        "À très vite,\nLe fondateur d'Omnividens\n\n"
        "Argos — on scanne, vous corrigez.\n"
    )


def book_meeting(request_id: str, *, poles_root: Path = POLES_DIR) -> Path | None:
    """Drafte la confirmation + l'invitation iCal d'une demande de RDV.

    Renvoie le chemin du draft ``.md`` (le ``.ics`` est écrit à côté), ou ``None``
    si la demande est introuvable. Idempotent : flippe le statut à ``drafted`` et
    ré-écrit les mêmes fichiers.
    """
    requests = load_requests(poles_root=poles_root)
    target = next((r for r in requests if r.request_id == request_id), None)
    if target is None:
        return None

    ics = build_ical_invite(
        uid=f"{target.request_id}@omnividens.fr",
        starts_at=target.starts_at,
        duration_minutes=target.duration_minutes,
        summary=f"Argos — RDV {target.company or target.attendee_name}",
        description="Démo / échange Argos (Omnividens).",
        location=target.location,
        organizer_email=ORGANIZER_EMAIL,
        organizer_name=ORGANIZER_NAME,
        attendee_email=target.attendee_email,
        attendee_name=target.attendee_name,
    )
    d = drafts_dir(poles_root=poles_root)
    ics_path = d / f"{request_id}.ics"
    ics_path.parent.mkdir(parents=True, exist_ok=True)
    ics_path.write_text(ics, encoding="utf-8")

    draft_path = d / f"{request_id}.md"
    write_markdown(
        draft_path,
        {
            "request_id": request_id,
            "to": target.attendee_email,
            "subject": f"Confirmation RDV Argos — {target.starts_at.date().isoformat()}",
            "attachment": f"{request_id}.ics",
            "starts_at": target.starts_at.isoformat(),
            "status": "drafted",
        },
        body=_confirmation_body(target),
    )

    updated = [
        MeetingRequest(
            request_id=r.request_id,
            attendee_email=r.attendee_email,
            attendee_name=r.attendee_name,
            company=r.company,
            starts_at=r.starts_at,
            duration_minutes=r.duration_minutes,
            location=r.location,
            status="drafted" if r.request_id == request_id else r.status,
        )
        for r in requests
    ]
    _save_requests(updated, poles_root=poles_root)
    return draft_path


def pending(requests: list[MeetingRequest]) -> list[MeetingRequest]:
    """Les demandes encore à traiter (statut ``pending``)."""
    return [r for r in requests if r.status == _PENDING]


__all__ = [
    "ORGANIZER_EMAIL",
    "ORGANIZER_NAME",
    "book_meeting",
    "drafts_dir",
    "load_requests",
    "pending",
    "requests_path",
]
