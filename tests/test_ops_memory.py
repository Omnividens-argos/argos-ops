"""Tests des endpoints mémoire de flotte du Cockpit (LOT 2).

Patchent ``FLEET_MEMORY_ROOT`` vers un ``tmp_path`` — aucune DB ni fichier
réel touché. Valident lecture / ajout / archivage + respect du graphe d'accès.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from argos_ops.ops_dashboard import app as app_module
from argos_ops.ops_dashboard.app import app

GRAPH = """# Fleet Memory

<!-- fleet-access-graph:start -->
```yaml
OutboundBot: [LeadEnricher, TrendSpotter]
OrchestratorBot: ["*"]
```
<!-- fleet-access-graph:end -->
"""


@pytest.fixture
def memory_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    (tmp_path / "MEMORY.md").write_text(GRAPH, encoding="utf-8")
    monkeypatch.setattr(app_module, "FLEET_MEMORY_ROOT", tmp_path)
    return tmp_path


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


# =============================================================================
# Lecture
# =============================================================================
def test_get_memory_unknown_agent_404(client: TestClient, memory_root: Path) -> None:
    assert client.get("/api/agents/NopeBot/memory").status_code == 404


def test_get_memory_empty(client: TestClient, memory_root: Path) -> None:
    resp = client.get("/api/agents/EmailBot/memory")
    assert resp.status_code == 200
    body = resp.json()
    assert body["bot"] == "EmailBot"
    assert body["own"] == []
    assert body["visible"] == []


# =============================================================================
# Ajout
# =============================================================================
def test_append_then_read(client: TestClient, memory_root: Path) -> None:
    resp = client.post(
        "/api/agents/EmailBot/memory",
        json={"body": "Acme veut un devis", "kind": "lead-signal", "tags": ["acme"]},
    )
    assert resp.status_code == 201
    fact = resp.json()
    assert fact["kind"] == "lead-signal"
    assert fact["source"] == "admin_panel"
    assert fact["tags"] == ["acme"]

    read = client.get("/api/agents/EmailBot/memory").json()
    assert len(read["own"]) == 1
    assert read["own"][0]["id"] == fact["id"]


def test_append_empty_body_400(client: TestClient, memory_root: Path) -> None:
    resp = client.post("/api/agents/EmailBot/memory", json={"body": "   "})
    assert resp.status_code == 400


def test_append_is_idempotent(client: TestClient, memory_root: Path) -> None:
    payload = {"body": "fait unique", "kind": "note"}
    id1 = client.post("/api/agents/EmailBot/memory", json=payload).json()["id"]
    id2 = client.post("/api/agents/EmailBot/memory", json=payload).json()["id"]
    assert id1 == id2
    assert len(client.get("/api/agents/EmailBot/memory").json()["own"]) == 1


# =============================================================================
# Archivage
# =============================================================================
def test_archive_fact(client: TestClient, memory_root: Path) -> None:
    fid = client.post(
        "/api/agents/EmailBot/memory", json={"body": "à archiver", "kind": "note"}
    ).json()["id"]
    resp = client.post(f"/api/agents/EmailBot/memory/{fid}/archive")
    assert resp.status_code == 200
    assert resp.json()["status"] == "archived"
    # Disparaît de la lecture active.
    assert client.get("/api/agents/EmailBot/memory").json()["own"] == []


def test_archive_missing_fact_404(client: TestClient, memory_root: Path) -> None:
    assert client.post("/api/agents/EmailBot/memory/deadbeef0000/archive").status_code == 404


# =============================================================================
# Graphe d'accès via l'API
# =============================================================================
def test_visible_memory_respects_graph(client: TestClient, memory_root: Path) -> None:
    client.post("/api/agents/LeadEnricher/memory", json={"body": "fiche acme", "kind": "note"})
    client.post("/api/agents/TrendSpotter/memory", json={"body": "trend vpn", "kind": "trend"})
    client.post("/api/agents/EmailBot/memory", json={"body": "privé email", "kind": "note"})

    body = client.get("/api/agents/OutboundBot/memory").json()
    visible_bots = {v["bot"] for v in body["visible"]}
    # OutboundBot lit LeadEnricher + TrendSpotter, mais PAS EmailBot.
    assert visible_bots == {"LeadEnricher", "TrendSpotter"}
    assert "EmailBot" not in visible_bots
    assert set(body["reads"]) == {"LeadEnricher", "TrendSpotter"}


def test_guardrail_bot_absent_from_graph_sees_only_itself(
    client: TestClient, memory_root: Path
) -> None:
    client.post("/api/agents/LeadEnricher/memory", json={"body": "secret", "kind": "note"})
    body = client.get("/api/agents/FinanceBot/memory").json()
    assert body["visible"] == []
    assert body["reads"] == []


def test_read_by_reverse_graph(client: TestClient, memory_root: Path) -> None:
    body = client.get("/api/agents/TrendSpotter/memory").json()
    # TrendSpotter est lu par OutboundBot (explicite) + OrchestratorBot (wildcard).
    assert "OutboundBot" in body["read_by"]
    assert "OrchestratorBot" in body["read_by"]
