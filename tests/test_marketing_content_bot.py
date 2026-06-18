"""Tests du script ``ContentBotScript`` (Marketing, archi v2, S2). Hermétique."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from argos_ops.poles.base import run_script
from argos_ops.poles.marketing import drafts
from argos_ops.poles.marketing.scripts.content_bot import ContentBotScript


def _validated_scheduled(root: Path, channel: str, title: str, when: datetime) -> drafts.Draft:
    d = drafts.create_draft(channel=channel, title=title, body="corps", poles_root=root)
    drafts.set_status(d.id, "validated", poles_root=root)
    scheduled = drafts.schedule_draft(d.id, when, poles_root=root)
    assert scheduled is not None
    return scheduled


async def test_publishes_due_validated_drafts(tmp_path: Path) -> None:
    now = datetime.now(UTC)
    due = _validated_scheduled(tmp_path, "mastodon", "Toot prêt", now - timedelta(hours=1))
    _validated_scheduled(tmp_path, "x", "Plus tard", now + timedelta(hours=1))  # futur

    result = await run_script(ContentBotScript(poles_root=tmp_path, now=now))

    assert result.status == "success"
    assert len(result.written) == 1
    assert result.written[0].kind == "publication"
    assert "mastodon" in result.written[0].tags
    # Le draft échu est passé en published ; le futur reste validated.
    assert drafts.load_draft(due.id, poles_root=tmp_path).status == "published"  # type: ignore[union-attr]


async def test_idempotent_second_run_publishes_nothing(tmp_path: Path) -> None:
    now = datetime.now(UTC)
    _validated_scheduled(tmp_path, "linkedin", "Post", now - timedelta(hours=2))

    first = await run_script(ContentBotScript(poles_root=tmp_path, now=now))
    second = await run_script(ContentBotScript(poles_root=tmp_path, now=now))

    assert len(first.written) == 1
    assert second.written == []  # déjà publié → plus rien d'échu


async def test_no_due_drafts_is_noop(tmp_path: Path) -> None:
    result = await run_script(ContentBotScript(poles_root=tmp_path))
    assert result.status == "success"
    assert result.written == []
