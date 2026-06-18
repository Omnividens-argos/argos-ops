"""Tests du journal des recos appliquées (shadow) du pôle Pub (archi v2, S3)."""

from __future__ import annotations

from pathlib import Path

from argos_ops.poles.pub import applied


def test_record_and_load(tmp_path: Path) -> None:
    rec = applied.record_applied(
        reco_id="google_search-saine-scale",
        platform="google_search",
        campaign="Saine",
        action="scale",
        eur_delta_week=105.0,
        rationale="CPA sous la cible",
        poles_root=tmp_path,
    )
    assert rec.mode == "shadow"
    loaded = applied.load_applied(poles_root=tmp_path)
    assert len(loaded) == 1
    assert loaded[0].id == "google_search-saine-scale"
    assert loaded[0].eur_delta_week == 105.0
    assert applied.applied_ids(poles_root=tmp_path) == {"google_search-saine-scale"}


def test_record_is_idempotent_preserves_applied_at(tmp_path: Path) -> None:
    first = applied.record_applied(
        reco_id="x",
        platform="meta",
        campaign="C",
        action="pause",
        eur_delta_week=-50.0,
        rationale="r",
        poles_root=tmp_path,
    )
    second = applied.record_applied(
        reco_id="x",
        platform="meta",
        campaign="C",
        action="pause",
        eur_delta_week=-50.0,
        rationale="r",
        poles_root=tmp_path,
    )
    assert first.applied_at == second.applied_at
    assert len(applied.load_applied(poles_root=tmp_path)) == 1


def test_empty_when_absent(tmp_path: Path) -> None:
    assert applied.load_applied(poles_root=tmp_path) == []
    assert applied.applied_ids(poles_root=tmp_path) == set()
