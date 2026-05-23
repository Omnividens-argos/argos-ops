"""Tests MediaListBuilder."""

from __future__ import annotations

from pathlib import Path

import yaml

from argos_ops.agents.media_list_builder import (
    ListReport,
    MediaContact,
    build_list_embed,
    build_report,
    load_media_list,
)
from argos_ops.notifications.discord import GREEN, YELLOW


def test_load_media_list_filters_invalid(tmp_path: Path) -> None:
    path = tmp_path / "m.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                "contacts": [
                    {"slug": "a", "name": "X", "outlet": "Z"},
                    {"slug": "b"},
                ]
            }
        ),
        encoding="utf-8",
    )
    assert len(load_media_list(path)) == 1


def test_media_contact_is_complete() -> None:
    full = MediaContact(slug="a", name="X", outlet="Z", beat="cyber", email="x@z")
    assert full.is_complete is True
    no_email = MediaContact(slug="b", name="X", outlet="Z", beat="cyber")
    assert no_email.is_complete is False


def test_build_report_groups_by_beat() -> None:
    contacts = [
        MediaContact(slug="a", name="A", outlet="x", beat="cyber", email="a@a"),
        MediaContact(slug="b", name="B", outlet="x", beat="cyber"),  # incomplet
        MediaContact(slug="c", name="C", outlet="x", beat="startup", email="c@c"),
    ]
    report = build_report(contacts)
    assert report.total == 3
    assert report.by_beat == {"cyber": 2, "startup": 1}
    assert report.incomplete == ["b"]


def test_build_list_embed_color() -> None:
    healthy = ListReport(total=15)
    healthy.by_beat["cyber"] = 15
    assert build_list_embed(healthy).color == GREEN
    incomplete = ListReport(total=20, incomplete=["x"])
    incomplete.by_beat["cyber"] = 20
    assert build_list_embed(incomplete).color == YELLOW
