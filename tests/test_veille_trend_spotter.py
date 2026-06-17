"""Tests du script Veille ``TrendSpotterScript`` (archi v2, S1).

Hermétique : mémoire de pôle sous ``tmp_path`` (``poles_root=``) et sources de
tendances injectées (``sources_path=``). Gabarit de référence pour les tests des
8 autres scripts Veille.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import yaml

from argos_ops.poles import memory
from argos_ops.poles.base import run_script
from argos_ops.poles.veille.scripts.trend_spotter import TrendSpotterScript


def _write_sources(path: Path, titles: list[str]) -> None:
    """Écrit un sources.yaml avec des items frais (publiés aujourd'hui)."""
    today = datetime.now(UTC).date().isoformat()
    items = [
        {"title": t, "url": f"https://cert.fr/{i}", "published_at": today, "weight": 1.0}
        for i, t in enumerate(titles)
    ]
    path.write_text(yaml.safe_dump({"items": items}), encoding="utf-8")


async def test_writes_top_trends_to_memory(tmp_path: Path) -> None:
    sources = tmp_path / "sources.yaml"
    _write_sources(sources, [f"Sujet {i}" for i in range(7)])

    result = await run_script(TrendSpotterScript(poles_root=tmp_path, sources_path=sources))

    assert result.status == "success"
    # Top 5 retenus sur 7 frais.
    assert len(result.written) == 5
    assert all(r.kind == "trend" for r in result.written)
    assert all("cyber" in r.tags for r in result.written)


async def test_top3_are_important(tmp_path: Path) -> None:
    sources = tmp_path / "sources.yaml"
    _write_sources(sources, [f"Sujet {i}" for i in range(5)])

    result = await run_script(TrendSpotterScript(poles_root=tmp_path, sources_path=sources))

    important = [r for r in result.written if r.important]
    assert len(important) == 3


async def test_idempotent_no_duplicate(tmp_path: Path) -> None:
    sources = tmp_path / "sources.yaml"
    _write_sources(sources, ["Faille Ivanti", "Ransomware Akira"])

    await run_script(TrendSpotterScript(poles_root=tmp_path, sources_path=sources))
    await run_script(TrendSpotterScript(poles_root=tmp_path, sources_path=sources))

    records = await memory.read_memory("veille", "trend_spotter", poles_root=tmp_path)
    assert len(records) == 2  # deux runs, pas de doublon (hash de corps stable)


async def test_empty_sources_writes_nothing(tmp_path: Path) -> None:
    result = await run_script(
        TrendSpotterScript(poles_root=tmp_path, sources_path=tmp_path / "absent.yaml")
    )
    assert result.status == "success"
    assert result.written == []


async def test_stale_items_filtered_out(tmp_path: Path) -> None:
    sources = tmp_path / "sources.yaml"
    old = (datetime.now(UTC).date() - timedelta(days=60)).isoformat()
    sources.write_text(
        yaml.safe_dump({"items": [{"title": "Vieux sujet", "url": "u", "published_at": old}]}),
        encoding="utf-8",
    )
    result = await run_script(TrendSpotterScript(poles_root=tmp_path, sources_path=sources))
    assert result.written == []
