"""Tests de ``GET /api/poles/handoffs/incoming`` (scan cross-pôle des handoffs).

Hermétique : app minimale (router ``poles`` seul) + ``POLES_DIR`` du module
patché vers ``tmp_path``. ``list_poles`` est ré-aiguillé vers ``tmp_path`` pour
que ``_require_pole`` (validation source/cible du POST) voie les pôles scaffold.
"""

from __future__ import annotations

import functools
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from argos_ops.ops_dashboard.api import poles as poles_api
from argos_ops.poles import config as poles_config


def _scaffold_pole(root: Path, pole: str, name: str) -> None:
    d = root / pole
    d.mkdir(parents=True, exist_ok=True)
    (d / "pole.yaml").write_text(
        f"id: {pole}\nname: {name}\nagent:\n  name: {name}Agent\n  skills: []\n"
        f"scripts: []\nreads_cross_pole: []\nfront_tools: [memory_table]\n",
        encoding="utf-8",
    )


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setattr(poles_api, "POLES_DIR", tmp_path)
    # ``_require_pole`` (POST) appelle ``list_poles`` sans poles_root → on le
    # ré-aiguille vers tmp_path pour que veille/marketing soient reconnus.
    monkeypatch.setattr(
        poles_api,
        "list_poles",
        functools.partial(poles_config.list_poles, poles_root=tmp_path),
    )
    _scaffold_pole(tmp_path, "veille", "Veille")
    _scaffold_pole(tmp_path, "marketing", "Marketing")

    app = FastAPI()
    app.include_router(poles_api.router)
    yield TestClient(app)


def _post_handoff(client: TestClient, source: str, target: str, note: str | None) -> dict[str, str]:
    r = client.post(
        f"/api/poles/{source}/handoff",
        json={"record_id": "rec-1", "target_pole": target, "note": note},
    )
    assert r.status_code == 201, r.text
    body: dict[str, str] = r.json()
    return body


def test_incoming_returns_handoff_for_target(client: TestClient) -> None:
    created = _post_handoff(client, "veille", "marketing", "CVE chaude")

    r = client.get("/api/poles/handoffs/incoming", params={"pole": "marketing"})
    assert r.status_code == 200
    items = r.json()
    assert len(items) == 1
    item = items[0]
    assert item["id"] == created["id"]
    assert item["source_pole"] == "veille"
    assert item["target_pole"] == "marketing"
    assert item["record_id"] == "rec-1"
    assert item["note"] == "CVE chaude"
    # Forme IncomingHandoff : pas de champ ``pole`` brut.
    assert "pole" not in item


def test_incoming_empty_for_other_pole(client: TestClient) -> None:
    _post_handoff(client, "veille", "marketing", None)

    r = client.get("/api/poles/handoffs/incoming", params={"pole": "veille"})
    assert r.status_code == 200
    assert r.json() == []


def test_incoming_no_filter_returns_all(client: TestClient) -> None:
    _post_handoff(client, "veille", "marketing", "a")
    _post_handoff(client, "marketing", "veille", "b")

    r = client.get("/api/poles/handoffs/incoming")
    assert r.status_code == 200
    items = r.json()
    assert {i["source_pole"] for i in items} == {"veille", "marketing"}
    assert len(items) == 2


def test_incoming_newest_first(client: TestClient) -> None:
    # Deux handoffs distincts (record_id différent → fichiers différents).
    client.post(
        "/api/poles/veille/handoff",
        json={"record_id": "old", "target_pole": "marketing", "note": "x"},
    )
    client.post(
        "/api/poles/veille/handoff",
        json={"record_id": "new", "target_pole": "marketing", "note": "y"},
    )
    # Réécrit les ``created_at`` pour ordonner déterministement.
    import json as _json

    handoffs_dir = poles_api.POLES_DIR / "veille" / poles_api.HANDOFFS_DIRNAME
    paths = sorted(handoffs_dir.glob("*.json"))
    assert len(paths) == 2
    stamps = ["2026-01-01T00:00:00+00:00", "2026-06-19T00:00:00+00:00"]
    newest_ids: list[str] = []
    for path, stamp in zip(paths, stamps, strict=True):
        data = _json.loads(path.read_text(encoding="utf-8"))
        data["created_at"] = stamp
        path.write_text(_json.dumps(data), encoding="utf-8")
        if stamp == stamps[1]:
            newest_ids.append(data["id"])

    items = client.get("/api/poles/handoffs/incoming", params={"pole": "marketing"}).json()
    assert items[0]["id"] == newest_ids[0]


def test_post_handoff_unknown_source_is_404(client: TestClient) -> None:
    r = client.post(
        "/api/poles/inexistant/handoff",
        json={"record_id": "r", "target_pole": "marketing", "note": None},
    )
    assert r.status_code == 404
