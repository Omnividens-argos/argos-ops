"""Tests de l'API cockpit du pôle Marketing (archi v2, S2).

Hermétique : app minimale (router Marketing seul, sans la DB de app.py) +
``POLES_DIR`` / ``ENGAGEMENT_PATH`` du module patchés vers ``tmp_path``.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
import yaml
from fastapi import FastAPI
from fastapi.testclient import TestClient

from argos_ops.ops_dashboard.api import marketing as mkt
from argos_ops.poles.marketing import drafts


def _scaffold_marketing_pole(root: Path) -> None:
    d = root / "marketing"
    d.mkdir(parents=True, exist_ok=True)
    (d / "pole.yaml").write_text(
        "id: marketing\nname: Marketing\nagent:\n  name: MarketingAgent\n  skills: []\n"
        "scripts: []\nreads_cross_pole: [veille]\nfront_tools: [memory_table, validation_queue]\n",
        encoding="utf-8",
    )


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setattr(mkt, "POLES_DIR", tmp_path)
    _scaffold_marketing_pole(tmp_path)  # load_context lit le pole.yaml (cross-pôle)
    eng = tmp_path / "engagement.yaml"
    today = datetime.now(UTC).date().isoformat()
    eng.write_text(
        yaml.safe_dump(
            {
                "posts": [
                    {
                        "posted_at": f"{today}T08:00:00Z",
                        "platform": "linkedin",
                        "url": "u",
                        "impressions": 1000,
                        "engagements": 80,
                        "clicks": 30,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(mkt, "ENGAGEMENT_PATH", eng)

    # Un draft de départ.
    drafts.create_draft(channel="linkedin", title="Premier post", body="corps", poles_root=tmp_path)

    app = FastAPI()
    app.include_router(mkt.router)
    yield TestClient(app)


def test_overview_shape(client: TestClient) -> None:
    r = client.get("/api/poles/marketing/overview")
    assert r.status_code == 200
    data = r.json()
    assert len(data["channels"]) == 8
    assert data["counts"]["drafts"] == 1
    assert data["counts"]["pending"] == 1
    assert data["charter"]["domain"] == "omnividens.fr"
    assert len(data["engagement"]) == 1


def test_create_validate_schedule_flow(client: TestClient) -> None:
    created = client.post(
        "/api/poles/marketing/drafts",
        json={"channel": "x", "title": "CVE nginx", "body": "court"},
    )
    assert created.status_code == 201
    draft_id = created.json()["id"]

    val = client.post(f"/api/poles/marketing/drafts/{draft_id}/validate")
    assert val.status_code == 200
    assert val.json()["status"] == "validated"

    sched = client.post(
        f"/api/poles/marketing/drafts/{draft_id}/schedule",
        json={"scheduled_for": "2026-07-01T09:00:00Z"},
    )
    assert sched.status_code == 200
    assert sched.json()["scheduled_for"].startswith("2026-07-01")

    overview = client.get("/api/poles/marketing/overview").json()
    assert overview["counts"]["scheduled"] == 1


def test_edit_draft(client: TestClient) -> None:
    overview = client.get("/api/poles/marketing/overview").json()
    draft_id = overview["drafts"][0]["id"]
    r = client.put(
        f"/api/poles/marketing/drafts/{draft_id}",
        json={"title": "Titre modifié", "body": "nouveau corps"},
    )
    assert r.status_code == 200
    assert r.json()["title"] == "Titre modifié"
    assert r.json()["body"] == "nouveau corps"


def test_create_unknown_channel_is_400(client: TestClient) -> None:
    r = client.post(
        "/api/poles/marketing/drafts",
        json={"channel": "tiktok", "title": "x", "body": "y"},
    )
    assert r.status_code == 400


def test_validate_missing_draft_is_404(client: TestClient) -> None:
    r = client.post("/api/poles/marketing/drafts/inexistant/validate")
    assert r.status_code == 404


def test_kb_put_then_delete(client: TestClient) -> None:
    put = client.put(
        "/api/poles/marketing/kb/pitch",
        json={"title": "Pitch", "body": "on scanne, vous corrigez", "tags": ["pitch"]},
    )
    assert put.status_code == 200
    assert put.json()["slug"] == "pitch"

    overview = client.get("/api/poles/marketing/overview").json()
    assert any(k["slug"] == "pitch" for k in overview["kb"])

    deleted = client.delete("/api/poles/marketing/kb/pitch")
    assert deleted.status_code == 204
    assert client.delete("/api/poles/marketing/kb/pitch").status_code == 404


def test_published_draft_is_immutable(client: TestClient, tmp_path: Path) -> None:
    d = drafts.create_draft(channel="linkedin", title="Déjà publié", body="x", poles_root=tmp_path)
    drafts.set_status(d.id, "published", poles_root=tmp_path)
    assert client.post(f"/api/poles/marketing/drafts/{d.id}/validate").status_code == 409
    assert (
        client.put(f"/api/poles/marketing/drafts/{d.id}", json={"body": "edit"}).status_code == 409
    )
    assert (
        client.post(f"/api/poles/marketing/drafts/{d.id}/schedule", json={"scheduled_for": None})
    ).status_code == 409


def test_kb_slug_is_normalized_server_side(client: TestClient) -> None:
    # Slug exotique reçu → re-slugifié côté serveur (nom de fichier canonique).
    r = client.put(
        "/api/poles/marketing/kb/Pitch Accentué",
        json={"title": "X", "body": "y", "tags": []},
    )
    assert r.status_code == 200
    assert r.json()["slug"] == "pitch-accentue"


def test_charter_put_persists(client: TestClient) -> None:
    payload = {
        "tagline": "Nouvelle tagline",
        "domain": "omnividens.fr",
        "voice": "ton",
        "principles": ["p1"],
        "avoid": ["a1"],
        "banned_terms": ["peur"],
        "ai_disclosure": "IA",
    }
    r = client.put("/api/poles/marketing/charter", json=payload)
    assert r.status_code == 200
    overview = client.get("/api/poles/marketing/overview").json()
    assert overview["charter"]["tagline"] == "Nouvelle tagline"
