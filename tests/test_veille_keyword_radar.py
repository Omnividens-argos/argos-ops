"""Tests du script Veille ``KeywordRadarScript`` (archi v2).

Hermétique : mémoire de pôle sous ``tmp_path`` (``poles_root=``) et fichiers
d'entrée injectés (``keywords_path=`` / ``history_path=``). Aucun réseau : le
script ne fait que lire/écrire des YAML locaux.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from argos_ops.poles import memory
from argos_ops.poles.base import run_script
from argos_ops.poles.veille.scripts.keyword_radar import (
    KeywordRadarScript,
    diff_positions,
    load_history,
    load_keywords,
    save_history,
)


def _write_keywords(path: Path, entries: list[dict[str, object]]) -> None:
    path.write_text(yaml.safe_dump({"keywords": entries}), encoding="utf-8")


# =============================================================================
# Helpers déterministes purs
# =============================================================================
def test_load_keywords_filters_priority(tmp_path: Path) -> None:
    path = tmp_path / "kw.yaml"
    _write_keywords(
        path,
        [
            {"term": "pentest", "position": 5, "priority": "high"},
            {"term": "obscure", "position": 99, "priority": "low"},
            {"term": "no-pos", "priority": "high"},
        ],
    )
    assert load_keywords(path) == {"pentest": 5}


def test_load_keywords_absent_returns_empty(tmp_path: Path) -> None:
    assert load_keywords(tmp_path / "absent.yaml") == {}


def test_diff_positions_marks_new_and_moves() -> None:
    moves = diff_positions({"a": 5, "b": 10}, {"a": 12})
    by_kw = {m.keyword: m for m in moves}
    assert by_kw["a"].delta == 7  # monté de 7 places (12 -> 5)
    assert by_kw["b"].is_new is True
    assert by_kw["b"].delta == 0


def test_save_and_load_history_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "h.yaml"
    save_history({"x": 7, "y": 12}, path)
    assert load_history(path) == {"x": 7, "y": 12}


# =============================================================================
# run() — écriture mémoire
# =============================================================================
async def test_loss_over_5_is_important(tmp_path: Path) -> None:
    kw = tmp_path / "kw.yaml"
    hist = tmp_path / "h.yaml"
    _write_keywords(kw, [{"term": "pentest", "position": 20, "priority": "high"}])
    save_history({"pentest": 10}, hist)  # delta = -10 -> perte sévère

    result = await run_script(
        KeywordRadarScript(poles_root=tmp_path, keywords_path=kw, history_path=hist)
    )

    assert result.status == "success"
    assert len(result.written) == 1
    rec = result.written[0]
    assert rec.kind == "seo_movement"
    assert rec.important is True
    assert "loss" in rec.tags


async def test_new_keyword_detected_not_important(tmp_path: Path) -> None:
    kw = tmp_path / "kw.yaml"
    hist = tmp_path / "h.yaml"
    _write_keywords(kw, [{"term": "scan-asv", "position": 8, "priority": "high"}])
    # pas d'historique -> keyword nouveau

    result = await run_script(
        KeywordRadarScript(poles_root=tmp_path, keywords_path=kw, history_path=hist)
    )

    assert len(result.written) == 1
    rec = result.written[0]
    assert rec.important is False
    assert "new" in rec.tags
    assert "nouveau keyword" in rec.body


async def test_strong_gain_recorded_not_important(tmp_path: Path) -> None:
    kw = tmp_path / "kw.yaml"
    hist = tmp_path / "h.yaml"
    _write_keywords(kw, [{"term": "pentest", "position": 3, "priority": "high"}])
    save_history({"pentest": 12}, hist)  # delta = +9 -> gain fort

    result = await run_script(
        KeywordRadarScript(poles_root=tmp_path, keywords_path=kw, history_path=hist)
    )

    assert len(result.written) == 1
    rec = result.written[0]
    assert rec.important is False
    assert "gain" in rec.tags


async def test_small_move_writes_nothing_but_updates_history(tmp_path: Path) -> None:
    kw = tmp_path / "kw.yaml"
    hist = tmp_path / "h.yaml"
    _write_keywords(kw, [{"term": "pentest", "position": 7, "priority": "high"}])
    save_history({"pentest": 9}, hist)  # delta = +2 -> non significatif

    result = await run_script(
        KeywordRadarScript(poles_root=tmp_path, keywords_path=kw, history_path=hist)
    )

    assert result.written == []
    # l'historique est tout de même réécrit avec la position courante
    assert load_history(hist) == {"pentest": 7}


async def test_idempotent_no_duplicate(tmp_path: Path) -> None:
    kw = tmp_path / "kw.yaml"
    hist = tmp_path / "h.yaml"
    _write_keywords(kw, [{"term": "pentest", "position": 20, "priority": "high"}])
    save_history({"pentest": 10}, hist)

    await run_script(KeywordRadarScript(poles_root=tmp_path, keywords_path=kw, history_path=hist))
    # Le 1er run a réécrit l'historique avec la position courante (20). On remet
    # l'historique précédent pour reproduire EXACTEMENT le même mouvement au 2e run.
    save_history({"pentest": 10}, hist)
    await run_script(KeywordRadarScript(poles_root=tmp_path, keywords_path=kw, history_path=hist))

    records = await memory.read_memory("veille", "keyword_radar", poles_root=tmp_path)
    assert len(records) == 1  # même corps -> hash stable, pas de doublon


async def test_empty_keywords_writes_nothing_and_history_untouched(tmp_path: Path) -> None:
    kw = tmp_path / "kw.yaml"
    hist = tmp_path / "h.yaml"
    _write_keywords(kw, [{"term": "low-prio", "position": 5, "priority": "low"}])
    save_history({"existing": 4}, hist)

    result = await run_script(
        KeywordRadarScript(poles_root=tmp_path, keywords_path=kw, history_path=hist)
    )

    assert result.status == "success"
    assert result.written == []
    records = await memory.read_memory("veille", "keyword_radar", poles_root=tmp_path)
    assert records == []
    # aucun keyword courant -> save_history n'est pas appelé, historique intact
    assert load_history(hist) == {"existing": 4}
