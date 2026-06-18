"""Tests du script Veille ``IntentSignalsScript`` (archi v2).

Hermétique : mémoire de pôle sous ``tmp_path`` (``poles_root=``), sources
injectées (``sources_path=``) et réseau toujours mocké (``_fetch`` monkeypatché
dans le namespace du module). Aucune requête HTTP réelle.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
import yaml

from argos_ops.exceptions import AgentDataSourceError
from argos_ops.poles import memory
from argos_ops.poles.base import run_script
from argos_ops.poles.veille.scripts import intent_signals
from argos_ops.poles.veille.scripts.intent_signals import (
    IntentSignalsScript,
    _load_sources,
    _parse_date,
    _parse_rss,
    _score_relevance,
)

# --- Fixtures RSS (calquées sur le test legacy, ASCII, aucun appel réseau) ---
_RSS_HOT = b"""<?xml version="1.0" encoding="utf-8"?>
<rss>
  <channel>
    <item>
      <title>Ransomware sur PME SaaS francaise</title>
      <description>Une PME francaise touchee par un ransomware, fuite RGPD.</description>
      <pubDate>Tue, 19 May 2026 14:32:00 +0000</pubDate>
      <link>https://cert.fr/hot</link>
    </item>
    <item>
      <title></title>
    </item>
  </channel>
</rss>
"""

_RSS_COLD = b"""<?xml version="1.0" encoding="utf-8"?>
<rss>
  <channel>
    <item>
      <title>Communique neutre</title>
      <description>Information generale sans signal.</description>
      <pubDate>Tue, 19 May 2026 14:32:00 +0000</pubDate>
      <link>https://example.com/cold</link>
    </item>
  </channel>
</rss>
"""


def _write_sources(path: Path, feeds: dict[str, list[str]]) -> None:
    path.write_text(yaml.safe_dump(feeds), encoding="utf-8")


# --- Helpers purs portés ------------------------------------------------------
def test_score_relevance_baseline_30() -> None:
    assert _score_relevance("titre neutre", "summary neutre") == 30


def test_score_relevance_icp_weighting() -> None:
    # saas, pme, rgpd (3 hits) -> bonus 30 ; ransomware/breach/fuite -> +10.
    # base 30 + 30 + 10 = 70.
    assert _score_relevance("Ransomware sur PME SaaS française", "fuite RGPD") == 70


def test_parse_date_rfc822_and_iso() -> None:
    assert _parse_date("Tue, 19 May 2026 14:32:00 +0000") == date(2026, 5, 19)
    assert _parse_date("2026-05-23") == date(2026, 5, 23)
    assert _parse_date("not a date") is None


def test_parse_rss_extracts_signals() -> None:
    signals = _parse_rss(_RSS_HOT, kind="breach")
    assert len(signals) == 1  # l'item sans titre est ignoré
    assert signals[0].kind == "breach"
    assert signals[0].published_at == date(2026, 5, 19)
    assert signals[0].source_url == "https://cert.fr/hot"


def test_load_sources_raises_on_malformed(tmp_path: Path) -> None:
    bad = tmp_path / "sources.yaml"
    bad.write_text("- not a mapping\n", encoding="utf-8")
    with pytest.raises(AgentDataSourceError):
        _load_sources(bad)


# --- run() : intégration hermétique ------------------------------------------
async def test_writes_signals_and_marks_important(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sources = tmp_path / "sources.yaml"
    _write_sources(sources, {"breach": ["https://cert.fr/feed"]})

    async def _fake_fetch(url: str, timeout: float = 8.0) -> bytes | None:
        return _RSS_HOT

    monkeypatch.setattr(intent_signals, "_fetch", _fake_fetch)

    result = await run_script(IntentSignalsScript(poles_root=tmp_path, sources_path=sources))

    assert result.status == "success"
    assert len(result.written) == 1
    rec = result.written[0]
    assert rec.kind == "intent_signal"
    assert rec.tags == ("intent", "breach")
    assert rec.important is True  # score 70 >= seuil 70
    assert rec.source == "https://cert.fr/hot"


async def test_low_score_signal_not_important(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sources = tmp_path / "sources.yaml"
    _write_sources(sources, {"fundraise": ["https://example.com/feed"]})

    async def _fake_fetch(url: str, timeout: float = 8.0) -> bytes | None:
        return _RSS_COLD

    monkeypatch.setattr(intent_signals, "_fetch", _fake_fetch)

    result = await run_script(IntentSignalsScript(poles_root=tmp_path, sources_path=sources))

    assert len(result.written) == 1
    assert result.written[0].important is False  # score 30 < 70


async def test_idempotent_no_duplicate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    sources = tmp_path / "sources.yaml"
    _write_sources(sources, {"breach": ["https://cert.fr/feed"]})

    async def _fake_fetch(url: str, timeout: float = 8.0) -> bytes | None:
        return _RSS_HOT

    monkeypatch.setattr(intent_signals, "_fetch", _fake_fetch)

    script = IntentSignalsScript(poles_root=tmp_path, sources_path=sources)
    await run_script(script)
    await run_script(script)

    records = await memory.read_memory("veille", "intent_signals", poles_root=tmp_path)
    assert len(records) == 1  # deux runs, pas de doublon (hash de corps stable)


async def test_empty_sources_writes_nothing(tmp_path: Path) -> None:
    result = await run_script(
        IntentSignalsScript(poles_root=tmp_path, sources_path=tmp_path / "absent.yaml")
    )
    assert result.status == "success"
    assert result.written == []
    records = await memory.read_memory("veille", "intent_signals", poles_root=tmp_path)
    assert records == []
