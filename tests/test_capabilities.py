"""Tests du module capabilities (P21, file-based — D-033)."""

from __future__ import annotations

from pathlib import Path

import pytest

from argos_ops import fleet_memory
from argos_ops.capabilities.consume import consume_capabilities, write_back
from argos_ops.capabilities.loader import (
    effective_read_rules,
    find_write_back_rule,
    load_capabilities,
)
from argos_ops.capabilities.models import CapabilityRule
from argos_ops.exceptions import CapabilityDeniedError

GRAPH = """# Fleet Memory

<!-- fleet-access-graph:start -->
```yaml
OutboundBot: [EmailBot, LeadEnricher]
StrategyBot: ["*"]
```
<!-- fleet-access-graph:end -->
"""

CAPS_YAML = """capabilities:
  - subject: OutboundBot
    object: EmailBot
    permission: read
    kind_filter: [lead-signal]
    tag_filter: [inbound]
    enabled: true
  - subject: OutboundBot
    object: LeadEnricher
    permission: read
    enabled: false
  - subject: BurnRateMonitor
    object: AdBot
    permission: write_back
    enabled: true
"""


@pytest.fixture
def caps_path(tmp_path: Path) -> Path:
    p = tmp_path / "agent_capabilities.yaml"
    p.write_text(CAPS_YAML, encoding="utf-8")
    return p


@pytest.fixture
def memory_root(tmp_path: Path) -> Path:
    root = tmp_path / "fleet_memory"
    root.mkdir()
    (root / "MEMORY.md").write_text(GRAPH, encoding="utf-8")
    return root


# =============================================================================
# Loader
# =============================================================================
def test_load_capabilities_parses_and_skips_malformed(tmp_path: Path) -> None:
    p = tmp_path / "c.yaml"
    p.write_text(
        "capabilities:\n"
        "  - subject: A\n    object: B\n    permission: read\n"
        "  - subject: X\n    permission: bogus\n"  # invalide (pas d'object, perm KO)
        "  - not_a_dict\n",
        encoding="utf-8",
    )
    rules = load_capabilities(p)
    assert len(rules) == 1
    assert rules[0].subject == "A" and rules[0].object == "B"


def test_load_capabilities_missing_file(tmp_path: Path) -> None:
    assert load_capabilities(tmp_path / "absent.yaml") == []


def test_capability_rule_matches_fact_filters() -> None:
    rule = CapabilityRule(
        subject="A",
        object="B",
        permission="read",
        kind_filter=("lead-signal",),
        tag_filter=("inbound",),
    )
    assert rule.matches_fact(kind="lead-signal", tags=("inbound", "email"))
    assert not rule.matches_fact(kind="objection", tags=("inbound",))  # mauvais kind
    assert not rule.matches_fact(kind="lead-signal", tags=("outbound",))  # tag manquant


# =============================================================================
# effective_read_rules : défaut ALLOW graphe + filtre + deny override
# =============================================================================
def test_effective_read_rules_default_allow_from_graph(caps_path: Path) -> None:
    rules = load_capabilities(caps_path)
    graph = {"OutboundBot": ["EmailBot", "LeadEnricher"]}
    allowed = effective_read_rules("OutboundBot", rules, graph)
    # EmailBot : règle de filtre explicite ; LeadEnricher : deny override (enabled=false)
    assert "EmailBot" in allowed and allowed["EmailBot"] is not None
    assert "LeadEnricher" not in allowed  # retiré par la règle enabled=false


def test_effective_read_rules_wildcard(caps_path: Path) -> None:
    rules = load_capabilities(caps_path)
    graph = {"StrategyBot": ["*"], "OutboundBot": ["EmailBot"]}
    allowed = effective_read_rules("StrategyBot", rules, graph)
    assert "OutboundBot" in allowed  # « * » voit les autres clés du graphe


def test_find_write_back_rule(caps_path: Path) -> None:
    rules = load_capabilities(caps_path)
    assert find_write_back_rule("BurnRateMonitor", "AdBot", rules) is not None
    assert find_write_back_rule("BurnRateMonitor", "EmailBot", rules) is None


# =============================================================================
# consume_capabilities (read + filtres) sur une mémoire réelle
# =============================================================================
@pytest.mark.asyncio
async def test_consume_capabilities_applies_filters(caps_path: Path, memory_root: Path) -> None:
    await fleet_memory.append_fact(
        "EmailBot",
        "lead inbound chaud",
        kind="lead-signal",
        tags=("inbound",),
        root=memory_root,
    )
    await fleet_memory.append_fact(
        "EmailBot",
        "objection prix",
        kind="objection",
        tags=("pricing",),
        root=memory_root,
    )
    out = await consume_capabilities(
        "OutboundBot", capabilities_path=caps_path, memory_root=memory_root
    )
    assert set(out) == {"EmailBot"}  # LeadEnricher deny-override, filtre kind/tag appliqué
    bodies = [f.body for f in out["EmailBot"]]
    assert bodies == ["lead inbound chaud"]  # l'objection est filtrée


# =============================================================================
# write_back : DENY par défaut, ALLOW si règle enabled
# =============================================================================
@pytest.mark.asyncio
async def test_write_back_denied_without_rule(caps_path: Path, memory_root: Path) -> None:
    with pytest.raises(CapabilityDeniedError):
        await write_back(
            "BurnRateMonitor",
            "EmailBot",
            "budget_adjust",
            "cap 30€",
            capabilities_path=caps_path,
            memory_root=memory_root,
        )


@pytest.mark.asyncio
async def test_write_back_allowed_writes_advice_fact(caps_path: Path, memory_root: Path) -> None:
    fact = await write_back(
        "BurnRateMonitor",
        "AdBot",
        "budget_adjust",
        "Cap conseillé 30€/j (runway -2 mois)",
        capabilities_path=caps_path,
        memory_root=memory_root,
    )
    assert fact.kind == "advice.budget_adjust"
    assert fact.source == "BurnRateMonitor (write_back)"
    mem = await fleet_memory.read_memory("AdBot", root=memory_root)
    assert any(f.kind == "advice.budget_adjust" for f in mem.active_facts)
