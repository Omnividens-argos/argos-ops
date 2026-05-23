"""Tests unitaires de ``argos_ops.agents.intent_signals`` (P22.H)."""

from __future__ import annotations

from datetime import date

from argos_ops.agents.intent_signals import (
    SignalStats,
    _parse_date,
    _parse_rss,
    _score_relevance,
    build_signals_embed,
)


def test_score_relevance_baseline_30() -> None:
    assert _score_relevance("titre neutre", "summary neutre") == 30


def test_score_relevance_bonus_keywords() -> None:
    # _ICP_KEYWORDS matches : saas, pme, rgpd (3 hits) → bonus 30.
    # ransomware/breach/fuite/leak → +10 (appliqué une fois).
    # Total : base 30 + 30 + 10 = 70.
    s = _score_relevance("Ransomware sur PME SaaS française", "fuite RGPD")
    assert s == 70


def test_parse_date_rfc822() -> None:
    d = _parse_date("Tue, 19 May 2026 14:32:00 +0000")
    assert d == date(2026, 5, 19)


def test_parse_date_iso() -> None:
    assert _parse_date("2026-05-23") == date(2026, 5, 23)


def test_parse_date_returns_none_for_garbage() -> None:
    assert _parse_date("not a date") is None


def test_parse_rss_extracts_signals() -> None:
    xml = """<?xml version="1.0" encoding="utf-8"?>
<rss>
  <channel>
    <item>
      <title>Ransomware sur PME SaaS</title>
      <description>Une PME française touchée par un ransomware.</description>
      <pubDate>Tue, 19 May 2026 14:32:00 +0000</pubDate>
      <link>https://cert.fr/x</link>
    </item>
    <item>
      <title></title>
    </item>
  </channel>
</rss>
""".encode()
    signals = _parse_rss(xml, kind="breach")
    assert len(signals) == 1
    assert signals[0].kind == "breach"
    assert signals[0].published_at == date(2026, 5, 19)


def test_build_signals_embed_color_orange_above_70() -> None:
    embed = build_signals_embed(
        SignalStats(captured=3, top_relevance=80, by_kind={"breach": 3}),
        [
            {
                "kind": "breach",
                "title": "Acme breach",
                "summary": "",
                "published_at": "2026-05-23",
                "source_url": "",
                "relevance_score": 80,
            }
        ],
    )
    assert embed.color == 0xE67E22  # ORANGE


def test_build_signals_embed_color_green_when_empty() -> None:
    embed = build_signals_embed(SignalStats(captured=0, top_relevance=0), [])
    assert embed.color == 0x2ECC71
