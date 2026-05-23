"""Tests unitaires de ``argos_ops.agents.meeting_booker`` (P22.H)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import yaml

from argos_ops.agents.meeting_booker import (
    BookingStats,
    _draft_meeting_email,
    _load_requests,
    _persist_requests,
    build_booking_embed,
)
from argos_ops.sales.models import MeetingRequest


def _request() -> MeetingRequest:
    return MeetingRequest(
        request_id="acme-marc-2026-06-04",
        attendee_email="marc@acme.fr",
        attendee_name="Marc Dupont",
        company="Acme SA",
        starts_at=datetime(2026, 6, 4, 14, 0, tzinfo=UTC),
        duration_minutes=30,
    )


def test_draft_meeting_email_writes_md_and_ics(tmp_path: Path) -> None:
    drafts_dir = tmp_path / "drafts"
    draft_path = _draft_meeting_email(
        _request(),
        organizer_email="contact@omnividens.fr",
        organizer_name="Argos par Omnividens",
        drafts_dir=drafts_dir,
    )
    assert draft_path.exists()
    ics_path = drafts_dir / "acme-marc-2026-06-04.ics"
    assert ics_path.exists()
    md_content = draft_path.read_text(encoding="utf-8")
    assert "marc@acme.fr" in md_content
    assert "Démo Argos confirmée" in md_content
    ics_content = ics_path.read_text(encoding="utf-8")
    assert "BEGIN:VCALENDAR" in ics_content
    assert "marc@acme.fr" in ics_content


def test_load_and_persist_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "requests.yaml"
    _persist_requests(path, [_request()])
    loaded = _load_requests(path)
    assert len(loaded) == 1
    assert loaded[0].attendee_email == "marc@acme.fr"
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert raw["requests"][0]["status"] == "pending"


def test_build_booking_embed_color_green_when_no_drafts() -> None:
    embed = build_booking_embed(BookingStats(pending_seen=0, drafts_created=0))
    assert embed.color == 0x2ECC71


def test_build_booking_embed_color_yellow_with_drafts() -> None:
    embed = build_booking_embed(BookingStats(pending_seen=2, drafts_created=2, drafts=["a", "b"]))
    assert embed.color == 0xF1C40F
