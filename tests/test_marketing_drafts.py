"""Tests du store de drafts du pôle Marketing (archi v2, S2). Hermétique (tmp_path)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from argos_ops.poles.marketing import drafts


def test_create_and_load_roundtrip(tmp_path: Path) -> None:
    d = drafts.create_draft(
        channel="linkedin", title="NIS2 expliquée à un dirigeant", body="corps", poles_root=tmp_path
    )
    assert d.id == "linkedin-nis2-expliquee-a-un-dirigeant"  # slug translittère les accents
    assert d.status == "draft"
    loaded = drafts.load_draft(d.id, poles_root=tmp_path)
    assert loaded is not None
    assert loaded.title == "NIS2 expliquée à un dirigeant"
    assert loaded.body == "corps"


def test_slugify_strips_accents() -> None:
    assert drafts.slugify("Preuves & chiffres clés") == "preuves-chiffres-cles"
    assert drafts.slugify("   ") == "draft"


def test_validate_reject_edit(tmp_path: Path) -> None:
    d = drafts.create_draft(channel="x", title="CVE nginx", body="court", poles_root=tmp_path)
    assert drafts.set_status(d.id, "validated", poles_root=tmp_path).status == "validated"  # type: ignore[union-attr]
    assert drafts.set_status(d.id, "rejected", poles_root=tmp_path).status == "rejected"  # type: ignore[union-attr]
    edited = drafts.edit_draft(d.id, title="CVE nginx (maj)", body="plus long", poles_root=tmp_path)
    assert edited is not None
    assert edited.title == "CVE nginx (maj)"
    assert edited.body == "plus long"
    # created_at préservé, updated_at avancé.
    assert edited.created_at == d.created_at


def test_mutations_on_missing_return_none(tmp_path: Path) -> None:
    assert drafts.set_status("absent", "validated", poles_root=tmp_path) is None
    assert drafts.edit_draft("absent", title="x", poles_root=tmp_path) is None
    assert drafts.schedule_draft("absent", datetime.now(UTC), poles_root=tmp_path) is None


def test_schedule_and_unschedule(tmp_path: Path) -> None:
    d = drafts.create_draft(channel="mastodon", title="toot", body="b", poles_root=tmp_path)
    when = datetime.now(UTC) + timedelta(days=1)
    scheduled = drafts.schedule_draft(d.id, when, poles_root=tmp_path)
    assert scheduled is not None and scheduled.scheduled_for == when
    cleared = drafts.schedule_draft(d.id, None, poles_root=tmp_path)
    assert cleared is not None and cleared.scheduled_for is None


def test_find_publishable_respects_status_and_time(tmp_path: Path) -> None:
    now = datetime.now(UTC)
    past = now - timedelta(hours=1)
    future = now + timedelta(hours=1)

    # validated + échu → publiable
    a = drafts.create_draft(channel="linkedin", title="A", body="b", poles_root=tmp_path)
    drafts.set_status(a.id, "validated", poles_root=tmp_path)
    drafts.schedule_draft(a.id, past, poles_root=tmp_path)
    # validated + futur → pas encore
    b = drafts.create_draft(channel="x", title="B", body="b", poles_root=tmp_path)
    drafts.set_status(b.id, "validated", poles_root=tmp_path)
    drafts.schedule_draft(b.id, future, poles_root=tmp_path)
    # draft échu mais non validé → exclu
    c = drafts.create_draft(channel="meta", title="C", body="b", poles_root=tmp_path)
    drafts.schedule_draft(c.id, past, poles_root=tmp_path)
    # validated mais non planifié → exclu
    e = drafts.create_draft(channel="bluesky", title="E", body="b", poles_root=tmp_path)
    drafts.set_status(e.id, "validated", poles_root=tmp_path)

    ready = drafts.find_publishable(now, poles_root=tmp_path)
    assert [d.id for d in ready] == [a.id]


def test_load_drafts_skips_corrupt_file(tmp_path: Path) -> None:
    drafts.create_draft(channel="x", title="OK", body="b", poles_root=tmp_path)
    bad = drafts.drafts_dir(poles_root=tmp_path) / "bad.md"
    bad.write_text("---\nfoo: [unclosed\n---\n\nbody\n", encoding="utf-8")
    loaded = drafts.load_drafts(poles_root=tmp_path)  # best-effort : ignore le fautif
    assert len(loaded) == 1
    assert loaded[0].title == "OK"


def test_create_is_overwrite_idempotent_by_id(tmp_path: Path) -> None:
    drafts.create_draft(channel="linkedin", title="Même titre", body="v1", poles_root=tmp_path)
    drafts.create_draft(channel="linkedin", title="Même titre", body="v2", poles_root=tmp_path)
    all_drafts = drafts.load_drafts(poles_root=tmp_path)
    assert len(all_drafts) == 1
    assert all_drafts[0].body == "v2"
