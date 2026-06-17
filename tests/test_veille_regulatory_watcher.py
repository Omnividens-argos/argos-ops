"""Tests du script Veille ``RegulatoryWatcherScript`` (archi v2).

Hermétique : mémoire de pôle sous ``tmp_path`` (``poles_root=``), sources et
cache GUIDs injectés (``sources_path=`` / ``seen_path=``). Le réseau est mocké
en monkeypatchant ``fetch_source`` dans le namespace du module (jamais de
``feedparser`` ni de ``httpx`` réel).
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import pytest

from argos_ops.poles import memory
from argos_ops.poles.base import run_script
from argos_ops.poles.veille.scripts.regulatory_watcher import (
    DEFAULT_KEYWORDS,
    RegulatoryItem,
    RegulatorySource,
    RegulatoryWatcherScript,
    load_seen_guids,
    load_sources,
    match_keywords,
    save_seen_guids,
    select_new_items,
)

MODULE = "argos_ops.poles.veille.scripts.regulatory_watcher"


def _item(guid: str, title: str = "") -> RegulatoryItem:
    return RegulatoryItem(
        source="CNIL",
        guid=guid,
        title=title or guid,
        link=f"https://cnil.fr/{guid}",
        published_at=None,
        matched_keywords=["rgpd"],
    )


def _write_sources(path: Path) -> None:
    """Écrit un sources.yaml minimal avec une source CNIL."""
    path.write_text(
        "sources:\n"
        "  - name: CNIL\n"
        "    rss_url: https://www.cnil.fr/feed.xml\n"
        "keywords: [rgpd, cnil]\n",
        encoding="utf-8",
    )


# =============================================================================
# Helpers purs portés
# =============================================================================
def test_match_keywords_lowercases() -> None:
    matched = match_keywords("Texte RGPD et CYBER RESILIENCE", DEFAULT_KEYWORDS)
    assert "rgpd" in matched
    assert "cyber resilience" in matched


def test_match_keywords_returns_empty_when_no_match() -> None:
    assert match_keywords("texte sur la cuisine", DEFAULT_KEYWORDS) == []


def test_load_sources_returns_defaults_when_missing(tmp_path: Path) -> None:
    sources, keywords = load_sources(tmp_path / "absent.yaml")
    assert sources == []
    assert keywords == DEFAULT_KEYWORDS


def test_load_sources_parses_yaml(tmp_path: Path) -> None:
    path = tmp_path / "sources.yaml"
    path.write_text(
        "sources:\n"
        "  - name: CNIL\n"
        "    rss_url: https://www.cnil.fr/feed.xml\n"
        "keywords: [rgpd, cnil, custom-kw]\n",
        encoding="utf-8",
    )
    sources, keywords = load_sources(path)
    assert len(sources) == 1
    assert sources[0].rss_url == "https://www.cnil.fr/feed.xml"
    assert "custom-kw" in keywords


def test_seen_guids_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "seen.json"
    save_seen_guids({"a", "b"}, path=path)
    reloaded = load_seen_guids(path=path)
    assert reloaded == {"a", "b"}


def test_seen_guids_trims_to_max_kept(tmp_path: Path) -> None:
    path = tmp_path / "seen.json"
    save_seen_guids({f"g{i}" for i in range(20)}, path=path, max_kept=5)
    reloaded = load_seen_guids(path=path)
    assert len(reloaded) == 5


def test_select_new_items_filters_seen() -> None:
    items = [_item("a"), _item("b"), _item("c")]
    new = select_new_items(items, seen={"a"})
    assert {i.guid for i in new} == {"b", "c"}


# =============================================================================
# run()
# =============================================================================
def _patch_fetch_source(monkeypatch: pytest.MonkeyPatch, items: Sequence[RegulatoryItem]) -> None:
    async def _fake_fetch_source(
        source: RegulatorySource, keywords: tuple[str, ...]
    ) -> list[RegulatoryItem]:
        return list(items)

    monkeypatch.setattr(f"{MODULE}.fetch_source", _fake_fetch_source)


async def test_empty_sources_writes_nothing(tmp_path: Path) -> None:
    result = await run_script(
        RegulatoryWatcherScript(
            poles_root=tmp_path,
            sources_path=tmp_path / "absent.yaml",
            seen_path=tmp_path / "seen.json",
        )
    )
    assert result.status == "success"
    assert result.written == []


async def test_run_writes_new_items_and_updates_seen(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sources = tmp_path / "sources.yaml"
    _write_sources(sources)
    seen_path = tmp_path / "seen.json"
    _patch_fetch_source(monkeypatch, [_item("a", "RGPD update"), _item("b", "NIS2 transposition")])

    result = await run_script(
        RegulatoryWatcherScript(poles_root=tmp_path, sources_path=sources, seen_path=seen_path)
    )

    assert result.status == "success"
    assert len(result.written) == 2
    assert all(r.kind == "regulatory" for r in result.written)
    assert all("regulatory" in r.tags for r in result.written)
    assert all(r.important is False for r in result.written)
    # Tous les GUIDs scannés sont persistés dans le cache anti-doublon.
    assert load_seen_guids(path=seen_path) == {"a", "b"}


async def test_run_skips_already_seen_items(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sources = tmp_path / "sources.yaml"
    _write_sources(sources)
    seen_path = tmp_path / "seen.json"
    save_seen_guids({"a"}, path=seen_path)
    _patch_fetch_source(monkeypatch, [_item("a", "déjà vu"), _item("b", "nouveau")])

    result = await run_script(
        RegulatoryWatcherScript(poles_root=tmp_path, sources_path=sources, seen_path=seen_path)
    )

    assert len(result.written) == 1
    assert result.written[0].source == "https://cnil.fr/b"


async def test_run_idempotent_no_duplicate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    sources = tmp_path / "sources.yaml"
    _write_sources(sources)
    seen_path = tmp_path / "seen.json"
    items = [_item("a", "Faille RGPD"), _item("b", "DORA")]

    # Premier passage : seen vide -> 2 nouvelles entrées + faits écrits.
    _patch_fetch_source(monkeypatch, items)
    first = await run_script(
        RegulatoryWatcherScript(poles_root=tmp_path, sources_path=sources, seen_path=seen_path)
    )
    assert len(first.written) == 2

    # Second passage : mêmes GUIDs -> déjà vus -> aucun nouveau fait.
    _patch_fetch_source(monkeypatch, items)
    second = await run_script(
        RegulatoryWatcherScript(poles_root=tmp_path, sources_path=sources, seen_path=seen_path)
    )
    assert second.written == []

    records = await memory.read_memory("veille", "regulatory_watcher", poles_root=tmp_path)
    assert len(records) == 2  # pas de doublon en mémoire
