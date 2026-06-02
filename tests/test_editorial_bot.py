"""Tests unitaires de :mod:`argos_ops.agents.editorial_bot`.

Couvre les helpers purs (find/parse/assign/build/write) et un run()
d'intégration (digest tmp → queue YAML), sans toucher au réseau ni à la DB
(``run()`` n'utilise pas la DB ; le wrapper ``run_agent`` n'est pas testé ici).
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
import yaml

from argos_ops.agents import editorial_bot
from argos_ops.agents.editorial_bot import (
    EditorialBot,
    EditorialPlan,
    assign_tasks,
    build_editorial_embed,
    build_queue_doc,
    find_latest_digest,
    parse_digest_topics,
    write_queue,
)

_NOW = datetime(2026, 6, 2, 8, 0, tzinfo=UTC)

_DIGEST = """# Argos — trends top 5 (2026-06-02)

1. Faille critique sur Ivanti EPM
2. Campagne de phishing massive
3. Nouveau module SAST tree-sitter
4. OWASP API Top 10 2025
5. Sauvegarde et ransomware en PME
"""


# --------------------------------------------------------------------------
# find_latest_digest
# --------------------------------------------------------------------------


def test_find_latest_digest_none_when_dir_missing(tmp_path: Path) -> None:
    assert find_latest_digest(tmp_path / "nope") is None


def test_find_latest_digest_none_when_empty(tmp_path: Path) -> None:
    assert find_latest_digest(tmp_path) is None


def test_find_latest_digest_returns_most_recent(tmp_path: Path) -> None:
    (tmp_path / "digest-2026-05-30.md").write_text("x", encoding="utf-8")
    (tmp_path / "digest-2026-06-02.md").write_text("y", encoding="utf-8")
    (tmp_path / "digest-2026-06-01.md").write_text("z", encoding="utf-8")
    latest = find_latest_digest(tmp_path)
    assert latest is not None
    assert latest.name == "digest-2026-06-02.md"


# --------------------------------------------------------------------------
# parse_digest_topics
# --------------------------------------------------------------------------


def test_parse_digest_topics_extracts_numbered_lines(tmp_path: Path) -> None:
    path = tmp_path / "digest-2026-06-02.md"
    path.write_text(_DIGEST, encoding="utf-8")
    topics = parse_digest_topics(path)
    assert topics == [
        "Faille critique sur Ivanti EPM",
        "Campagne de phishing massive",
        "Nouveau module SAST tree-sitter",
        "OWASP API Top 10 2025",
        "Sauvegarde et ransomware en PME",
    ]


def test_parse_digest_topics_ignores_non_numbered(tmp_path: Path) -> None:
    path = tmp_path / "d.md"
    path.write_text("# titre\n\ndu texte\n- puce\n1. vrai sujet\n", encoding="utf-8")
    assert parse_digest_topics(path) == ["vrai sujet"]


# --------------------------------------------------------------------------
# assign_tasks
# --------------------------------------------------------------------------


def test_assign_tasks_grand_public_goes_to_meta_else_rotation() -> None:
    topics = [
        "Faille critique sur Ivanti EPM",  # → linkedin (rot 0)
        "Campagne de phishing massive",  # phishing → meta
        "Nouveau module SAST tree-sitter",  # → mastodon (rot 1)
        "OWASP API Top 10 2025",  # → bluesky (rot 2)
        "Sauvegarde et ransomware en PME",  # ransomware → meta
    ]
    tasks = assign_tasks(topics)
    assert [t["channel"] for t in tasks] == ["linkedin", "meta", "mastodon", "bluesky", "meta"]
    # writer + slash cohérents avec le canal
    assert tasks[0]["writer"] == "linkedin-writer"
    assert tasks[0]["slash"] == "/draft-linkedin"
    assert tasks[1]["writer"] == "meta-writer"
    assert tasks[1]["slash"] == "/draft-meta"
    # le topic est conservé tel quel
    assert tasks[1]["topic"] == "Campagne de phishing massive"
    # angle non vide
    assert all(t["angle"] for t in tasks)


def test_assign_tasks_rotation_wraps_after_four() -> None:
    topics = [f"Sujet technique {i}" for i in range(6)]  # aucun grand-public
    channels = [t["channel"] for t in assign_tasks(topics)]
    assert channels == ["linkedin", "mastodon", "bluesky", "x", "linkedin", "mastodon"]


def test_assign_tasks_never_routes_to_truth() -> None:
    topics = [f"Sujet {i}" for i in range(10)]
    assert all(t["channel"] != "truth" for t in assign_tasks(topics))


# --------------------------------------------------------------------------
# build_queue_doc + write_queue
# --------------------------------------------------------------------------


def test_build_queue_doc_shape() -> None:
    tasks = assign_tasks(["Faille Ivanti"])
    digest = Path("data/trends/digest-2026-06-02.md")
    doc = build_queue_doc(tasks, source_digest=digest, now=_NOW)
    assert doc["generated_at"] == _NOW.isoformat()
    assert doc["source_digest"] == "digest-2026-06-02.md"  # name only, pas le path complet
    assert doc["mode"] == "shadow"
    assert doc["tasks"] == tasks


def test_write_queue_roundtrips(tmp_path: Path) -> None:
    tasks = assign_tasks(["Faille Ivanti", "Phishing massif"])
    doc = build_queue_doc(tasks, source_digest=Path("digest-2026-06-02.md"), now=_NOW)
    path = write_queue(doc, now=_NOW, out_dir=tmp_path)
    assert path.name == "queue-2026-06-02.yaml"
    reloaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert reloaded["mode"] == "shadow"
    assert len(reloaded["tasks"]) == 2
    assert reloaded["tasks"][1]["channel"] == "meta"  # phishing


# --------------------------------------------------------------------------
# build_editorial_embed
# --------------------------------------------------------------------------


def test_build_editorial_embed_green_with_tasks() -> None:
    tasks = assign_tasks(["Faille Ivanti"])
    plan = EditorialPlan(source_digest=Path("d.md"), tasks=tasks, queue_path=Path("queue-x.yaml"))
    embed = build_editorial_embed(plan)
    assert embed.color == editorial_bot.GREEN
    assert "EditorialBot" in embed.title
    assert any("/draft-linkedin" in f.value for f in embed.fields)


# --------------------------------------------------------------------------
# EditorialBot.run() — intégration
# --------------------------------------------------------------------------


async def _noop_send_embed(*args: Any, **kwargs: Any) -> None:
    return None


async def test_run_no_digest_returns_zero_tasks(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(editorial_bot, "TRENDS_DIR", tmp_path / "trends")
    monkeypatch.setattr(editorial_bot, "QUEUE_DIR", tmp_path / "editorial")
    monkeypatch.setattr(editorial_bot, "send_embed", _noop_send_embed)

    result = await EditorialBot().run()
    assert result.status == "success"
    assert result.output_summary == "digest=none tasks=0"
    assert not (tmp_path / "editorial").exists()  # rien écrit


async def test_run_writes_queue_from_digest(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    trends = tmp_path / "trends"
    trends.mkdir()
    (trends / "digest-2026-06-02.md").write_text(_DIGEST, encoding="utf-8")
    queue_dir = tmp_path / "editorial"
    monkeypatch.setattr(editorial_bot, "TRENDS_DIR", trends)
    monkeypatch.setattr(editorial_bot, "QUEUE_DIR", queue_dir)
    monkeypatch.setattr(editorial_bot, "send_embed", _noop_send_embed)

    result = await EditorialBot().run()
    assert result.status == "success"
    assert result.output_summary == "digest=yes tasks=5"

    queue_files = list(queue_dir.glob("queue-*.yaml"))
    assert len(queue_files) == 1
    doc = yaml.safe_load(queue_files[0].read_text(encoding="utf-8"))
    assert doc["source_digest"] == "digest-2026-06-02.md"
    assert [t["channel"] for t in doc["tasks"]] == [
        "linkedin",
        "meta",
        "mastodon",
        "bluesky",
        "meta",
    ]
