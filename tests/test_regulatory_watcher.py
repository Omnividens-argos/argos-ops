"""Tests unitaires de :mod:`argos_ops.agents.regulatory_watcher` (P22.D)."""

from __future__ import annotations

from pathlib import Path

from argos_ops.agents.regulatory_watcher import (
    DEFAULT_KEYWORDS,
    RegulatoryItem,
    build_report,
    load_seen_guids,
    load_sources,
    match_keywords,
    save_seen_guids,
    select_new_items,
)
from argos_ops.notifications.discord import GREEN, YELLOW


def _item(guid: str, title: str = "") -> RegulatoryItem:
    return RegulatoryItem(
        source="CNIL",
        guid=guid,
        title=title or guid,
        link=f"https://cnil.fr/{guid}",
        published_at=None,
        matched_keywords=["rgpd"],
    )


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


def test_build_report_green_when_no_new() -> None:
    report = build_report([], total_scanned=10)
    assert report.alert_color == GREEN
    assert report.should_alert is False


def test_build_report_yellow_when_new() -> None:
    report = build_report([_item("a")], total_scanned=10)
    assert report.alert_color == YELLOW
    assert report.should_alert is True
