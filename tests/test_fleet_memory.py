"""Tests unitaires de ``argos_ops.fleet_memory`` (Cockpit LOT 1)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from argos_ops.fleet_memory import (
    BotMemory,
    append_fact,
    archive_fact,
    compute_fact_id,
    delete_fact,
    list_bots,
    load_access_graph,
    read_memory,
    remember,
    resolve_visible_bots,
    visible_memory,
)

GRAPH = """# Fleet Memory

<!-- fleet-access-graph:start -->
```yaml
OutboundBot: [LeadEnricher, TrendSpotter]
OrchestratorBot: ["*"]
```
<!-- fleet-access-graph:end -->
"""


def _write_graph(root: Path, content: str = GRAPH) -> None:
    (root / "MEMORY.md").write_text(content, encoding="utf-8")


# =============================================================================
# Identité / idempotence
# =============================================================================
def test_compute_fact_id_stable_under_whitespace_and_case() -> None:
    a = compute_fact_id("Acme veut un  DEVIS.")
    b = compute_fact_id("acme veut un devis.")
    assert a == b
    assert len(a) == 12


# =============================================================================
# Écriture + lecture
# =============================================================================
@pytest.mark.asyncio
async def test_append_then_read(tmp_path: Path) -> None:
    fact = await append_fact(
        "EmailBot",
        "Acme veut un devis 50 scans/mois.",
        kind="lead-signal",
        source="run#1",
        confidence="high",
        tags=("acme",),
        root=tmp_path,
    )
    mem = await read_memory("EmailBot", root=tmp_path)
    assert isinstance(mem, BotMemory)
    assert len(mem.facts) == 1
    stored = mem.facts[0]
    assert stored.id == fact.id
    assert stored.kind == "lead-signal"
    assert stored.confidence == "high"
    assert stored.tags == ("acme",)
    assert stored.status == "active"


@pytest.mark.asyncio
async def test_append_is_idempotent(tmp_path: Path) -> None:
    body = "Objection pricing récurrente côté PME."
    f1 = await append_fact("EmailBot", body, kind="objection", root=tmp_path)
    f2 = await append_fact(
        "EmailBot", "  objection PRICING récurrente  côté  PME.  ", kind="objection", root=tmp_path
    )
    assert f1.id == f2.id
    mem = await read_memory("EmailBot", root=tmp_path)
    assert len(mem.facts) == 1  # un seul fichier malgré le double append
    files = list((tmp_path / "EmailBot" / "facts").glob("*.md"))
    assert len(files) == 1


@pytest.mark.asyncio
async def test_append_empty_body_raises(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        await append_fact("EmailBot", "   ", kind="note", root=tmp_path)


@pytest.mark.asyncio
async def test_read_missing_bot_returns_empty(tmp_path: Path) -> None:
    mem = await read_memory("GhostBot", root=tmp_path)
    assert mem.bot == "GhostBot"
    assert mem.facts == []


@pytest.mark.asyncio
async def test_facts_sorted_recent_first(tmp_path: Path) -> None:
    await append_fact(
        "EmailBot",
        "vieux fait",
        kind="note",
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        root=tmp_path,
    )
    await append_fact(
        "EmailBot",
        "fait récent",
        kind="note",
        created_at=datetime(2026, 6, 1, tzinfo=UTC),
        root=tmp_path,
    )
    mem = await read_memory("EmailBot", root=tmp_path)
    assert mem.facts[0].body == "fait récent"
    assert mem.facts[1].body == "vieux fait"


@pytest.mark.asyncio
async def test_archived_excluded_unless_requested(tmp_path: Path) -> None:
    await append_fact("EmailBot", "fait actif", kind="note", root=tmp_path)
    # Simule une archivage façon MemoryCurator (P20) : patch le frontmatter.
    fact_file = next((tmp_path / "EmailBot" / "facts").glob("*.md"))
    fact_file.write_text(
        fact_file.read_text(encoding="utf-8").replace("status: active", "status: archived"),
        encoding="utf-8",
    )
    assert (await read_memory("EmailBot", root=tmp_path)).facts == []
    assert len((await read_memory("EmailBot", root=tmp_path, include_archived=True)).facts) == 1


# =============================================================================
# Se souvenir (remember — batch depuis un run)
# =============================================================================
@pytest.mark.asyncio
async def test_remember_persists_drafts(tmp_path: Path) -> None:
    stored = await remember(
        "TrendSpotter",
        [
            {"body": "Sujet chaud : faille VPN", "kind": "trend", "ttl_days": 21},
            {"body": "Sujet chaud : ransomware santé", "kind": "trend"},
        ],
        default_source="/run-trend-spot",
        root=tmp_path,
    )
    assert len(stored) == 2
    assert stored[0].source == "/run-trend-spot"
    assert stored[0].ttl_days == 21
    mem = await read_memory("TrendSpotter", root=tmp_path)
    assert len(mem.facts) == 2


@pytest.mark.asyncio
async def test_remember_skips_empty_body(tmp_path: Path) -> None:
    stored = await remember(
        "TrendSpotter",
        [{"body": "  "}, {"body": "vrai fait"}],
        root=tmp_path,
    )
    assert len(stored) == 1
    assert stored[0].body == "vrai fait"


@pytest.mark.asyncio
async def test_remember_is_idempotent(tmp_path: Path) -> None:
    draft = {"body": "fait répété", "kind": "trend"}
    await remember("TrendSpotter", [draft], root=tmp_path)
    await remember("TrendSpotter", [draft], root=tmp_path)
    mem = await read_memory("TrendSpotter", root=tmp_path)
    assert len(mem.facts) == 1


# =============================================================================
# Archivage (soft delete)
# =============================================================================
@pytest.mark.asyncio
async def test_archive_fact(tmp_path: Path) -> None:
    fact = await append_fact("EmailBot", "fait à archiver", kind="note", root=tmp_path)
    archived = await archive_fact("EmailBot", fact.id, root=tmp_path)
    assert archived is not None
    assert archived.status == "archived"
    assert archived.archived_at is not None
    # Exclu de la lecture active, présent avec include_archived.
    assert (await read_memory("EmailBot", root=tmp_path)).facts == []
    assert len((await read_memory("EmailBot", root=tmp_path, include_archived=True)).facts) == 1


@pytest.mark.asyncio
async def test_archive_missing_fact_returns_none(tmp_path: Path) -> None:
    assert await archive_fact("EmailBot", "deadbeef0000", root=tmp_path) is None


@pytest.mark.asyncio
async def test_archive_is_idempotent(tmp_path: Path) -> None:
    fact = await append_fact("EmailBot", "déjà archivé", kind="note", root=tmp_path)
    first = await archive_fact("EmailBot", fact.id, root=tmp_path)
    second = await archive_fact("EmailBot", fact.id, root=tmp_path)
    assert first is not None and second is not None
    assert first.archived_at == second.archived_at


# =============================================================================
# Suppression dure + pinned + list_bots
# =============================================================================
@pytest.mark.asyncio
async def test_delete_fact(tmp_path: Path) -> None:
    fact = await append_fact("EmailBot", "à supprimer", kind="note", root=tmp_path)
    assert await delete_fact("EmailBot", fact.id, root=tmp_path) is True
    assert (await read_memory("EmailBot", root=tmp_path)).facts == []
    # Re-supprimer = no-op False.
    assert await delete_fact("EmailBot", fact.id, root=tmp_path) is False


@pytest.mark.asyncio
async def test_pinned_roundtrip(tmp_path: Path) -> None:
    await append_fact("EmailBot", "fait important", kind="note", pinned=True, root=tmp_path)
    fact = (await read_memory("EmailBot", root=tmp_path)).facts[0]
    assert fact.pinned is True


@pytest.mark.asyncio
async def test_list_bots(tmp_path: Path) -> None:
    await append_fact("EmailBot", "a", kind="note", root=tmp_path)
    await append_fact("TrendSpotter", "b", kind="note", root=tmp_path)
    assert list_bots(root=tmp_path) == ["EmailBot", "TrendSpotter"]


# =============================================================================
# Graphe d'accès
# =============================================================================
@pytest.mark.asyncio
async def test_load_access_graph(tmp_path: Path) -> None:
    _write_graph(tmp_path)
    graph = await load_access_graph(root=tmp_path)
    assert graph["OutboundBot"] == ["LeadEnricher", "TrendSpotter"]
    assert graph["OrchestratorBot"] == ["*"]


@pytest.mark.asyncio
async def test_load_access_graph_missing_file(tmp_path: Path) -> None:
    assert await load_access_graph(root=tmp_path) == {}


@pytest.mark.asyncio
async def test_resolve_visible_includes_self(tmp_path: Path) -> None:
    _write_graph(tmp_path)
    visible = await resolve_visible_bots("OutboundBot", root=tmp_path)
    assert set(visible) == {"OutboundBot", "LeadEnricher", "TrendSpotter"}


@pytest.mark.asyncio
async def test_guardrail_bot_absent_from_graph_sees_only_itself(tmp_path: Path) -> None:
    _write_graph(tmp_path)
    await append_fact("LeadEnricher", "secret enrich", kind="note", root=tmp_path)
    # FinanceBot n'est pas dans le graphe → ne voit que lui-même.
    visible = await resolve_visible_bots("FinanceBot", root=tmp_path)
    assert visible == ["FinanceBot"]
    mem = await visible_memory("FinanceBot", root=tmp_path)
    assert set(mem.keys()) == {"FinanceBot"}
    assert "LeadEnricher" not in mem


@pytest.mark.asyncio
async def test_guardrail_cannot_read_undeclared_bot(tmp_path: Path) -> None:
    _write_graph(tmp_path)
    await append_fact("EmailBot", "donnée privée EmailBot", kind="note", root=tmp_path)
    # OutboundBot peut lire LeadEnricher + TrendSpotter, mais PAS EmailBot.
    visible = await resolve_visible_bots("OutboundBot", root=tmp_path)
    assert "EmailBot" not in visible


@pytest.mark.asyncio
async def test_wildcard_sees_all_bots_on_disk(tmp_path: Path) -> None:
    _write_graph(tmp_path)
    await append_fact("EmailBot", "a", kind="note", root=tmp_path)
    await append_fact("LeadEnricher", "b", kind="note", root=tmp_path)
    await append_fact("TrendSpotter", "c", kind="note", root=tmp_path)
    visible = await resolve_visible_bots("OrchestratorBot", root=tmp_path)
    # "*" → tous les dossiers bots présents + lui-même.
    assert {"EmailBot", "LeadEnricher", "TrendSpotter", "OrchestratorBot"} <= set(visible)


# =============================================================================
# Composition du « IN » mémoire
# =============================================================================
@pytest.mark.asyncio
async def test_visible_memory_composes_own_plus_allowed(tmp_path: Path) -> None:
    _write_graph(tmp_path)
    await append_fact("OutboundBot", "ma séquence", kind="note", root=tmp_path)
    await append_fact("LeadEnricher", "fiche acme", kind="note", root=tmp_path)
    await append_fact("TrendSpotter", "trend vpn", kind="note", root=tmp_path)
    mem = await visible_memory("OutboundBot", root=tmp_path)
    assert set(mem.keys()) == {"OutboundBot", "LeadEnricher", "TrendSpotter"}
    assert mem["LeadEnricher"].facts[0].body == "fiche acme"
