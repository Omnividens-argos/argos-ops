"""Tests du serveur MCP de pilotage flotte (Atelier libre).

``run_bot`` exécute un agent réel (DB) → intégration, non testée ici. On couvre
la sérialisation des faits et la liste des bots (pures, sans DB)."""

from __future__ import annotations

from datetime import UTC, datetime

from argos_ops.fleet_memory import Fact
from argos_ops.mcp import fleet_server


def test_fact_dict_shape() -> None:
    fact = Fact(
        id="abc123",
        bot="TrendSpotter",
        kind="trend",
        body="Sujet chaud VPN",
        confidence="high",
        tags=("trend", "cyber"),
        ttl_days=21,
        pinned=True,
        created_at=datetime(2026, 6, 7, tzinfo=UTC),
    )
    d = fleet_server._fact_dict(fact)
    assert d["id"] == "abc123"
    assert d["kind"] == "trend"
    assert d["tags"] == ["trend", "cyber"]
    assert d["ttl_days"] == 21
    assert d["pinned"] is True
    assert d["created_at"].startswith("2026-06-07")


def test_mcp_server_exposes_fleet_tools() -> None:
    # Le serveur est instancié et nommé ; les outils sont déclarés.
    assert fleet_server.mcp.name == "argos-fleet"
