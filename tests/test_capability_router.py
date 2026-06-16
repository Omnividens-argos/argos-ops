"""Tests de CapabilityRouter (audit du câblage inter-agents, P21)."""

from __future__ import annotations

from pathlib import Path

import pytest

from argos_ops import fleet_memory
from argos_ops.agents.capability_router import (
    audit_capabilities,
    build_capability_embed,
)
from argos_ops.notifications.discord import GREEN, YELLOW

GRAPH = """# Fleet Memory

<!-- fleet-access-graph:start -->
```yaml
OutboundBot: [EmailBot]
```
<!-- fleet-access-graph:end -->
"""


@pytest.fixture
def memory_root(tmp_path: Path) -> Path:
    root = tmp_path / "fleet_memory"
    root.mkdir()
    (root / "MEMORY.md").write_text(GRAPH, encoding="utf-8")
    return root


def _caps(tmp_path: Path, body: str) -> Path:
    p = tmp_path / "caps.yaml"
    p.write_text(body, encoding="utf-8")
    return p


@pytest.mark.asyncio
async def test_audit_silent_when_wiring_healthy(tmp_path: Path, memory_root: Path) -> None:
    # OutboundBot (graphe) lit EmailBot, qui a un fait matchant → câblage sain.
    await fleet_memory.append_fact(
        "EmailBot", "lead inbound", kind="lead-signal", tags=("inbound",), root=memory_root
    )
    caps = _caps(
        tmp_path,
        "capabilities:\n  - subject: OutboundBot\n    object: EmailBot\n"
        "    permission: read\n    kind_filter: [lead-signal]\n    tag_filter: [inbound]\n"
        "    enabled: true\n",
    )
    audit = await audit_capabilities(capabilities_path=caps, memory_root=memory_root)
    assert audit.should_alert is False
    assert audit.alert_color == GREEN
    assert not audit.orphan_rules and not audit.empty_wirings


@pytest.mark.asyncio
async def test_audit_flags_orphan_rule(tmp_path: Path, memory_root: Path) -> None:
    caps = _caps(
        tmp_path,
        "capabilities:\n  - subject: GhostBot\n    object: NopeBot\n    permission: read\n",
    )
    audit = await audit_capabilities(capabilities_path=caps, memory_root=memory_root)
    assert audit.should_alert is True
    assert audit.alert_color == YELLOW
    assert len(audit.orphan_rules) == 1
    assert "inconnu" in audit.orphan_rules[0][1]


@pytest.mark.asyncio
async def test_audit_flags_empty_wiring(tmp_path: Path, memory_root: Path) -> None:
    # Règle read valide mais EmailBot n'a aucun fait matchant → câblage à vide.
    caps = _caps(
        tmp_path,
        "capabilities:\n  - subject: OutboundBot\n    object: EmailBot\n"
        "    permission: read\n    kind_filter: [lead-signal]\n    enabled: true\n",
    )
    audit = await audit_capabilities(capabilities_path=caps, memory_root=memory_root)
    assert audit.should_alert is True
    assert len(audit.empty_wirings) == 1


@pytest.mark.asyncio
async def test_audit_flags_active_write_back(tmp_path: Path, memory_root: Path) -> None:
    await fleet_memory.append_fact(
        "EmailBot", "x", kind="lead-signal", tags=("inbound",), root=memory_root
    )
    caps = _caps(
        tmp_path,
        "capabilities:\n  - subject: OutboundBot\n    object: EmailBot\n"
        "    permission: write_back\n    enabled: true\n",
    )
    audit = await audit_capabilities(capabilities_path=caps, memory_root=memory_root)
    assert len(audit.write_back_active) == 1
    embed = build_capability_embed(audit)
    assert any("write_back" in f.name for f in embed.fields)
