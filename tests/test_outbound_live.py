"""Tests unitaires d'``argos_ops.agents.outbound_sender`` (P22.H P13.B)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

import yaml

from argos_ops.agents.outbound_sender import (
    SendStats,
    _persist_state,
    _read_touch_md,
    build_outbound_embed,
    determine_mode,
)
from argos_ops.outbound.models import SequenceState, Touch, TouchStep


@dataclass
class _StubSettings:
    email_user: str | None = "contact@omnividens.fr"
    email_password: object | None = object()  # SecretStr en prod
    outbound_live_mode: bool = False
    outbound_from_domain: str | None = None
    outbound_unsubscribe_secret: object | None = None


def test_determine_mode_disabled_when_no_credentials() -> None:
    settings = _StubSettings(email_user=None, email_password=None)
    assert determine_mode(settings) == "disabled"


def test_determine_mode_stage_by_default() -> None:
    settings = _StubSettings()
    assert determine_mode(settings) == "stage"


def test_determine_mode_live_when_all_flags_set() -> None:
    settings = _StubSettings(
        outbound_live_mode=True,
        outbound_from_domain="try-omnividens.com",
        outbound_unsubscribe_secret=object(),
    )
    assert determine_mode(settings) == "live"


def test_determine_mode_stage_if_live_mode_but_no_domain() -> None:
    settings = _StubSettings(
        outbound_live_mode=True,
        outbound_from_domain=None,
        outbound_unsubscribe_secret=object(),
    )
    assert determine_mode(settings) == "stage"


def test_read_touch_md_parses_frontmatter(tmp_path: Path) -> None:
    p = tmp_path / "touch.md"
    p.write_text("---\nsubject: Hello\nstatus: drafted\n---\n\nBody here.\n", encoding="utf-8")
    front, body = _read_touch_md(p)
    assert front == {"subject": "Hello", "status": "drafted"}
    assert body.startswith("Body here.")


def test_read_touch_md_returns_empty_front_when_no_frontmatter(tmp_path: Path) -> None:
    p = tmp_path / "touch.md"
    p.write_text("No frontmatter here.", encoding="utf-8")
    front, body = _read_touch_md(p)
    assert front == {}
    assert body == "No frontmatter here."


def test_persist_state_round_trip(tmp_path: Path) -> None:
    state = SequenceState(
        lead_slug="acme",
        full_name="Marc Dupont",
        domain="acme.fr",
        enriched_path=None,
        opt_out_token="deadbeef",
        sequence_status="active",
        touches=[
            Touch(
                step=TouchStep.DISCOVERY,
                scheduled_date=date(2026, 5, 23),
                status="sent",
                subject="Hello",
                body="Body",
                sent_at="2026-05-23T08:00:00+00:00",
            )
        ],
        created_at="2026-05-20T10:00:00+00:00",
    )
    path = tmp_path / "meta.yaml"
    _persist_state(path, state)
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert raw["full_name"] == "Marc Dupont"
    assert raw["touches"][0]["status"] == "sent"
    assert raw["touches"][0]["sent_at"] == "2026-05-23T08:00:00+00:00"


def test_build_outbound_embed_orange_on_failures() -> None:
    embed = build_outbound_embed(
        SendStats(sequences_scanned=1, touches_sent=0, failures=1), "stage"
    )
    assert embed.color == 0xE67E22  # ORANGE


def test_build_outbound_embed_yellow_when_sent() -> None:
    embed = build_outbound_embed(
        SendStats(sequences_scanned=1, touches_sent=2, sent_slugs=["a#1", "a#2"]),
        "stage",
    )
    assert embed.color == 0xF1C40F


def test_build_outbound_embed_green_when_nothing_sent() -> None:
    embed = build_outbound_embed(SendStats(sequences_scanned=1), "live")
    assert embed.color == 0x2ECC71
