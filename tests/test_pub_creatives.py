"""Tests de la file de créas du pôle Pub (archi v2, S3)."""

from __future__ import annotations

from pathlib import Path

from argos_ops.poles.pub import creatives
from argos_ops.poles.pub.creatives import Variant


def _variants() -> tuple[Variant, ...]:
    return (
        Variant(label="A", angle="tech", headline="Pentest continu", primary_text="corps A"),
        Variant(label="B", angle="ops", headline="Scan + remédiation", primary_text="corps B"),
    )


def test_slugify_translitterates() -> None:
    assert creatives.slugify("NIS2 expliquée aux DSI") == "nis2-expliquee-aux-dsi"
    assert creatives.slugify("") == "crea"


def test_create_and_load_roundtrip(tmp_path: Path) -> None:
    creatives.create_creative(
        platform="google_search",
        title="Pentest SaaS",
        variants=_variants(),
        objective="leads",
        persona="marc",
        brief="Brief de campagne",
        poles_root=tmp_path,
    )
    loaded = creatives.load_creative("google_search-pentest-saas", poles_root=tmp_path)
    assert loaded is not None
    assert loaded.status == "draft"
    assert loaded.platform == "google_search"
    assert loaded.objective == "leads"
    assert loaded.brief == "Brief de campagne"
    assert len(loaded.variants) == 2
    assert loaded.variants[0].label == "A"
    assert loaded.variants[0].headline == "Pentest continu"


def test_set_status_transitions(tmp_path: Path) -> None:
    creatives.create_creative(
        platform="meta", title="PME", variants=_variants(), poles_root=tmp_path
    )
    cid = "meta-pme"
    assert creatives.set_status(cid, "validated", poles_root=tmp_path).status == "validated"  # type: ignore[union-attr]
    assert creatives.set_status(cid, "live", poles_root=tmp_path).status == "live"  # type: ignore[union-attr]
    # Les variantes survivent aux transitions.
    assert len(creatives.load_creative(cid, poles_root=tmp_path).variants) == 2  # type: ignore[union-attr]


def test_set_status_missing_returns_none(tmp_path: Path) -> None:
    assert creatives.set_status("nope", "validated", poles_root=tmp_path) is None


def test_find_publishable_only_validated(tmp_path: Path) -> None:
    creatives.create_creative(platform="google_search", title="Draftee", poles_root=tmp_path)
    creatives.create_creative(platform="meta", title="Validee", poles_root=tmp_path)
    creatives.set_status("meta-validee", "validated", poles_root=tmp_path)
    pub = creatives.find_publishable(poles_root=tmp_path)
    assert [c.id for c in pub] == ["meta-validee"]


def test_load_creatives_empty_dir(tmp_path: Path) -> None:
    assert creatives.load_creatives(poles_root=tmp_path) == []
