"""Tests du serveur MCP de pilotage flotte (Atelier libre).

``run_bot`` exécute un agent réel (DB) → intégration, non testée ici. On couvre
la sérialisation des faits et la liste des bots (pures, sans DB)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

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


# =============================================================================
# remember_fact — garde-fous + écriture
# =============================================================================
@pytest.mark.asyncio
async def test_remember_fact_rejects_unknown_bot() -> None:
    result = await fleet_server.remember_fact("NopeBot", "un fait")
    assert result["status"] == "error"
    assert "NopeBot" in result["error"]


@pytest.mark.asyncio
async def test_remember_fact_rejects_empty_body() -> None:
    result = await fleet_server.remember_fact("EmailBot", "   ")
    assert result["status"] == "error"


@pytest.mark.asyncio
async def test_remember_fact_writes_with_atelier_source(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    async def fake_append(bot: str, body: str, **kwargs: object) -> Fact:
        captured.update({"bot": bot, "body": body, **kwargs})
        return Fact(id="abc123", bot=bot, kind=str(kwargs.get("kind")), body=body)

    monkeypatch.setattr(fleet_server, "append_fact", fake_append)
    result = await fleet_server.remember_fact(
        "EmailBot", "objection récurrente PME", kind="objection", tags=["pricing"]
    )
    assert result["status"] == "ok"
    assert captured["source"] == "atelier"
    assert captured["ttl_days"] == 180  # défaut appliqué
    assert captured["tags"] == ("pricing",)
