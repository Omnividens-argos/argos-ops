"""Tests unitaires de ``argos_ops.sales.ical`` (P22.H Sales Sprint 3)."""

from __future__ import annotations

from datetime import UTC, datetime

from argos_ops.sales.ical import build_ical_invite


def _sample_invite() -> str:
    return build_ical_invite(
        uid="acme-marc-2026-06-04@omnividens.fr",
        starts_at=datetime(2026, 6, 4, 14, 0, tzinfo=UTC),
        duration_minutes=30,
        summary="Argos — démo avec Acme SA",
        description="Démo Argos 30 min.",
        location="Visio (Jitsi)",
        organizer_email="contact@omnividens.fr",
        organizer_name="Argos par Omnividens",
        attendee_email="marc@acme.fr",
        attendee_name="Marc Dupont",
    )


def test_ical_has_required_lines() -> None:
    ics = _sample_invite()
    for needle in (
        "BEGIN:VCALENDAR",
        "END:VCALENDAR",
        "BEGIN:VEVENT",
        "END:VEVENT",
        "UID:acme-marc-2026-06-04@omnividens.fr",
        "DTSTART:20260604T140000Z",
        "DTEND:20260604T143000Z",
        "METHOD:REQUEST",
        "ATTENDEE",
        "marc@acme.fr",
    ):
        assert needle in ics, f"missing {needle}"


def test_ical_escapes_commas_and_newlines() -> None:
    ics = build_ical_invite(
        uid="x@y",
        starts_at=datetime(2026, 6, 4, 14, 0, tzinfo=UTC),
        duration_minutes=15,
        summary="Sujet, avec virgule",
        description="line1\nline2",
        location="Salle; A",
        organizer_email="o@y",
        organizer_name="O",
        attendee_email="a@y",
        attendee_name="A",
    )
    assert "Sujet\\, avec virgule" in ics
    assert "line1\\nline2" in ics
    assert "Salle\\; A" in ics


def test_ical_lines_end_with_crlf() -> None:
    ics = _sample_invite()
    assert ics.count("\r\n") >= 10
    assert "\r\nBEGIN:VEVENT\r\n" in ics
