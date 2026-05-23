"""Génération d'invitations iCalendar RFC 5545 pour MeetingBooker.

Implémenté en stdlib (pas de dépendance ``icalendar`` ajoutée) pour
respecter la contrainte 0 € D-009. Les champs implémentés sont ceux
qu'Outlook / Apple Mail / Gmail acceptent sans plainte :

- ``BEGIN:VCALENDAR`` / ``END:VCALENDAR``
- ``VERSION:2.0`` / ``PRODID``
- ``BEGIN:VEVENT`` / ``END:VEVENT``
- ``UID``, ``DTSTAMP``, ``DTSTART``, ``DTEND``, ``SUMMARY``,
  ``DESCRIPTION``, ``LOCATION``, ``ORGANIZER``, ``ATTENDEE``

Les newlines sont CRLF (RFC 5545 § 3.1) et les lignes > 75 octets sont
foldées avec un espace en début de ligne suivante.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

CRLF = "\r\n"
LINE_FOLD_BYTES = 75


def _fold_line(line: str) -> str:
    """Plie une ligne longue selon RFC 5545 § 3.1 (max 75 octets / ligne)."""
    encoded = line.encode("utf-8")
    if len(encoded) <= LINE_FOLD_BYTES:
        return line
    chunks: list[str] = []
    current = bytearray()
    for ch in encoded:
        current.append(ch)
        if len(current) >= LINE_FOLD_BYTES:
            chunks.append(current.decode("utf-8", errors="ignore"))
            current = bytearray()
    if current:
        chunks.append(current.decode("utf-8", errors="ignore"))
    return chunks[0] + CRLF + CRLF.join(" " + c for c in chunks[1:])


def _escape_text(value: str) -> str:
    """Escape les caractères réservés iCalendar (\\n, \\,, \\;, \\\\)."""
    return value.replace("\\", "\\\\").replace(",", "\\,").replace(";", "\\;").replace("\n", "\\n")


def _fmt_utc(dt: datetime) -> str:
    """Format ``YYYYMMDDTHHMMSSZ`` (RFC 5545 UTC) — input peut être naive."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")


def build_ical_invite(
    *,
    uid: str,
    starts_at: datetime,
    duration_minutes: int,
    summary: str,
    description: str,
    location: str,
    organizer_email: str,
    organizer_name: str,
    attendee_email: str,
    attendee_name: str,
) -> str:
    """Construit le payload ICS d'une invitation 1-attendee.

    Le résultat est typiquement attaché en pièce jointe
    ``invitation.ics`` ou inliné en ``text/calendar; method=REQUEST``
    dans l'email envoyé par MeetingBooker.

    ``uid`` doit être stable pour un même RDV (re-envoi = ``METHOD:REQUEST``
    avec mêmes UID → l'attendee voit la mise à jour, pas un nouveau).
    """
    ends_at = starts_at + timedelta(minutes=duration_minutes)
    now = datetime.now(UTC)
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Omnividens//Argos Ops MeetingBooker//FR",
        "METHOD:REQUEST",
        "CALSCALE:GREGORIAN",
        "BEGIN:VEVENT",
        f"UID:{uid}",
        f"DTSTAMP:{_fmt_utc(now)}",
        f"DTSTART:{_fmt_utc(starts_at)}",
        f"DTEND:{_fmt_utc(ends_at)}",
        f"SUMMARY:{_escape_text(summary)}",
        f"DESCRIPTION:{_escape_text(description)}",
        f"LOCATION:{_escape_text(location)}",
        f'ORGANIZER;CN="{_escape_text(organizer_name)}":mailto:{organizer_email}',
        f'ATTENDEE;CN="{_escape_text(attendee_name)}";RSVP=TRUE:mailto:{attendee_email}',
        "STATUS:CONFIRMED",
        "TRANSP:OPAQUE",
        "END:VEVENT",
        "END:VCALENDAR",
    ]
    return CRLF.join(_fold_line(ln) for ln in lines) + CRLF


__all__ = ["build_ical_invite"]
