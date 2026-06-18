"""Tests du script ``MediaListBuilderScript`` (Marketing, archi v2, S2). Hermétique."""

from __future__ import annotations

from pathlib import Path

import yaml

from argos_ops.poles.base import run_script
from argos_ops.poles.marketing.scripts.media_list_builder import (
    MediaListBuilderScript,
    build_report,
    load_media_list,
)


def _write_media(path: Path, contacts: list[dict[str, str]]) -> None:
    path.write_text(yaml.safe_dump({"contacts": contacts}), encoding="utf-8")


async def test_audit_flags_incomplete(tmp_path: Path) -> None:
    media = tmp_path / "media.yaml"
    _write_media(
        media,
        [
            {"slug": "a", "name": "A", "beat": "cyber", "email": "a@x.fr"},
            {"slug": "b", "name": "B", "beat": "cyber"},  # email manquant → incomplet
        ],
    )
    result = await run_script(MediaListBuilderScript(poles_root=tmp_path, media_list_path=media))

    assert result.status == "success"
    assert len(result.written) == 1
    fact = result.written[0]
    assert fact.kind == "media"
    assert fact.important is True  # incomplet OU < 10 contacts
    assert "incomplete" in fact.tags


async def test_absent_media_list_is_noop(tmp_path: Path) -> None:
    result = await run_script(
        MediaListBuilderScript(poles_root=tmp_path, media_list_path=tmp_path / "absent.yaml")
    )
    assert result.status == "success"
    assert result.written == []


def test_build_report_counts(tmp_path: Path) -> None:
    media = tmp_path / "m.yaml"
    _write_media(
        media,
        [
            {"slug": "a", "name": "A", "beat": "cyber", "email": "a@x.fr"},
            {"slug": "b", "name": "B", "beat": "tech", "email": "b@x.fr"},
            {"slug": "c", "name": "C", "beat": "", "email": ""},
        ],
    )
    report = build_report(load_media_list(media))
    assert report.total == 3
    assert report.by_beat["cyber"] == 1
    assert "c" in report.incomplete
