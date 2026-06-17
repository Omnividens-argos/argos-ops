"""Tests du script Veille ``PressMonitorScript`` (archi v2).

Hermétique : mémoire de pôle sous ``tmp_path`` (``poles_root=``) et fichier de
mentions injecté (``mentions_path=``). Aucun réseau (le legacy était déjà
shadow : lecture YAML pure). Calqué sur ``tests/test_veille_trend_spotter.py``.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from argos_ops.poles import memory
from argos_ops.poles.base import run_script
from argos_ops.poles.veille.scripts.press_monitor import (
    PressMention,
    PressMonitorScript,
    load_mentions,
    mark_ack,
)


def _write_mentions(path: Path, entries: list[dict[str, object]]) -> None:
    path.write_text(yaml.safe_dump({"mentions": entries}, allow_unicode=True), encoding="utf-8")


def test_load_mentions_parses_and_filters_invalid(tmp_path: Path) -> None:
    path = tmp_path / "m.yaml"
    _write_mentions(
        path,
        [
            {"id": "1", "source": "ZDNet", "url": "https://z/1", "title": "Argos lance"},
            {"source": "no-id"},  # ignoré (pas d'id)
            "pas-un-mapping",  # ignoré
        ],
    )
    mentions = load_mentions(path)
    assert len(mentions) == 1
    assert mentions[0].source == "ZDNet"
    assert mentions[0].status == "new"  # défaut
    assert mentions[0].sentiment == "neutral"  # défaut


def test_load_mentions_missing_file_returns_empty(tmp_path: Path) -> None:
    assert load_mentions(tmp_path / "absent.yaml") == []


def test_mark_ack_flips_only_targeted(tmp_path: Path) -> None:
    path = tmp_path / "m.yaml"
    mentions = [
        PressMention(id="1", source="A", url="u", title="t", status="new"),
        PressMention(id="2", source="B", url="u", title="t", status="new"),
    ]
    mark_ack(mentions, ack_ids={"1"}, path=path)
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    by_id = {m["id"]: m for m in raw["mentions"]}
    assert by_id["1"]["status"] == "ack"
    assert by_id["2"]["status"] == "new"


async def test_run_writes_fact_per_new_mention(tmp_path: Path) -> None:
    path = tmp_path / "m.yaml"
    _write_mentions(
        path,
        [
            {"id": "1", "source": "ZDNet", "url": "https://z/1", "title": "Argos lance"},
            {"id": "2", "source": "LeMagIT", "url": "https://l/2", "title": "Pentest auto"},
            {"id": "3", "source": "Old", "url": "u", "title": "Deja vu", "status": "ack"},
        ],
    )

    result = await run_script(PressMonitorScript(poles_root=tmp_path, mentions_path=path))

    assert result.status == "success"
    # 2 nouvelles sur 3 (la 3e est deja ack).
    assert len(result.written) == 2
    assert all(r.kind == "press" for r in result.written)
    assert all("press" in r.tags for r in result.written)
    assert result.summary == "total=3 new=2 negatives=0"


async def test_run_marks_important_on_negative(tmp_path: Path) -> None:
    path = tmp_path / "m.yaml"
    _write_mentions(
        path,
        [
            {
                "id": "1",
                "source": "Critique",
                "url": "https://c/1",
                "title": "Faille chez Argos",
                "sentiment": "negative",
            },
            {
                "id": "2",
                "source": "Neutre",
                "url": "https://n/2",
                "title": "Argos cite",
                "sentiment": "neutral",
            },
        ],
    )

    result = await run_script(PressMonitorScript(poles_root=tmp_path, mentions_path=path))

    important = [r for r in result.written if r.important]
    assert len(important) == 1
    assert "negative" in important[0].tags
    assert result.summary == "total=2 new=2 negatives=1"


async def test_run_marks_ack_in_rewritten_yaml(tmp_path: Path) -> None:
    path = tmp_path / "m.yaml"
    _write_mentions(
        path,
        [
            {"id": "1", "source": "ZDNet", "url": "u1", "title": "Argos lance"},
            {"id": "2", "source": "Old", "url": "u2", "title": "Deja vu", "status": "ack"},
        ],
    )

    await run_script(PressMonitorScript(poles_root=tmp_path, mentions_path=path))

    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    by_id = {m["id"]: m for m in raw["mentions"]}
    assert by_id["1"]["status"] == "ack"  # la nouvelle a ete acquittee
    assert by_id["2"]["status"] == "ack"  # l'ancienne reste ack


async def test_idempotent_second_run_writes_nothing(tmp_path: Path) -> None:
    path = tmp_path / "m.yaml"
    _write_mentions(
        path,
        [
            {"id": "1", "source": "ZDNet", "url": "u1", "title": "Argos lance"},
            {"id": "2", "source": "LeMagIT", "url": "u2", "title": "Pentest auto"},
        ],
    )

    first = await run_script(PressMonitorScript(poles_root=tmp_path, mentions_path=path))
    second = await run_script(PressMonitorScript(poles_root=tmp_path, mentions_path=path))

    assert len(first.written) == 2
    # Au 2e run, tout est ack -> rien de nouveau.
    assert second.written == []
    assert second.summary == "total=2 new=0 negatives=0"

    records = await memory.read_memory("veille", "press_monitor", poles_root=tmp_path)
    assert len(records) == 2  # pas de doublon


async def test_empty_input_writes_nothing(tmp_path: Path) -> None:
    result = await run_script(
        PressMonitorScript(poles_root=tmp_path, mentions_path=tmp_path / "absent.yaml")
    )
    assert result.status == "success"
    assert result.written == []
    assert result.summary == "total=0 new=0 negatives=0"
