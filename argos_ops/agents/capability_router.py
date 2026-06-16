"""CapabilityRouter — Capability Manager (P21, file-based / D-033).

Audite le câblage inter-agents déclaré dans ``data/agent_capabilities.yaml``
+ le graphe d'accès ``MEMORY.md``. Read-only : ne route rien lui-même (le
routage se fait quand chaque bot appelle :func:`consume_capabilities` au
début de son run) — ce bot **surveille la cohérence du câblage** et alerte
sur les anomalies :

- **règle orpheline** : subject/object n'est pas un agent connu de la flotte ;
- **câblage à vide** : une règle ``read`` pointe un object dont la mémoire ne
  contient (pour l'instant) aucun fait matchant les filtres ;
- **write_back actif** : signalé (risque comportemental — boucle douce).

Silence Discord si le câblage est sain. Embed jaune sinon. Cf. plan P21.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from loguru import logger

from argos_ops import fleet_memory
from argos_ops.agents._watcher_base import color_title, emit_alert_or_silence
from argos_ops.agents.base import BaseAgent, IOItem, RunResult
from argos_ops.capabilities.loader import (
    DEFAULT_CAPABILITIES_PATH,
    load_capabilities,
)
from argos_ops.capabilities.models import CapabilityRule
from argos_ops.notifications.discord import GREEN, YELLOW, Embed, EmbedField


@dataclass
class CapabilityAudit:
    """Résultat d'un passage — satisfait le Protocol ``WatcherReport``."""

    total_rules: int
    read_rules: int
    write_back_active: list[CapabilityRule]
    orphan_rules: list[tuple[CapabilityRule, str]]  # (règle, raison)
    empty_wirings: list[CapabilityRule]
    should_alert: bool
    alert_color: int
    summary: str = field(compare=False)


async def _known_agents(memory_root: Path) -> set[str]:
    """Agents « connus » : présents dans le graphe d'accès ou ayant une mémoire."""
    graph = await fleet_memory.load_access_graph(root=memory_root)
    known: set[str] = set(graph)
    for targets in graph.values():
        known.update(t for t in targets if t != fleet_memory.GRAPH_WILDCARD)
    known.update(fleet_memory.list_bots(root=memory_root))
    return known


async def audit_capabilities(
    *,
    capabilities_path: Path = DEFAULT_CAPABILITIES_PATH,
    memory_root: Path = fleet_memory.FLEET_MEMORY_DIR,
) -> CapabilityAudit:
    """Inspecte les règles + flag les anomalies (pure-ish : I/O lecture seule)."""
    rules = load_capabilities(capabilities_path)
    known = await _known_agents(memory_root)

    read_rules = [r for r in rules if r.permission == "read"]
    write_back_active = [r for r in rules if r.permission == "write_back" and r.enabled]
    orphan_rules: list[tuple[CapabilityRule, str]] = []
    empty_wirings: list[CapabilityRule] = []

    for rule in rules:
        missing = [a for a in (rule.subject, rule.object) if a not in known]
        if missing:
            orphan_rules.append((rule, f"agent(s) inconnu(s) : {', '.join(missing)}"))
            continue
        # Câblage read actif mais sans aucun fait matchant → à vide (info).
        if rule.permission == "read" and rule.enabled:
            mem = await fleet_memory.read_memory(rule.object, root=memory_root)
            if not any(rule.matches_fact(kind=f.kind, tags=f.tags) for f in mem.active_facts):
                empty_wirings.append(rule)

    should_alert = bool(orphan_rules or empty_wirings or write_back_active)
    summary = (
        f"{len(rules)} règle(s) · {len(read_rules)} read · "
        f"{len(write_back_active)} write_back actif(s) · "
        f"{len(orphan_rules)} orpheline(s) · {len(empty_wirings)} à vide"
    )
    return CapabilityAudit(
        total_rules=len(rules),
        read_rules=len(read_rules),
        write_back_active=write_back_active,
        orphan_rules=orphan_rules,
        empty_wirings=empty_wirings,
        should_alert=should_alert,
        alert_color=YELLOW if should_alert else GREEN,
        summary=summary,
    )


def build_capability_embed(audit: CapabilityAudit) -> Embed:
    fields: list[EmbedField] = []
    if audit.orphan_rules:
        lines = [f"• {r.subject} → {r.object} : {why}" for r, why in audit.orphan_rules[:8]]
        fields.append(EmbedField(name="Règles orphelines", value="\n".join(lines), inline=False))
    if audit.empty_wirings:
        lines = [
            f"• {r.subject} ← {r.object} ({', '.join(r.kind_filter) or 'tous kinds'})"
            for r in audit.empty_wirings[:8]
        ]
        fields.append(EmbedField(name="Câblages à vide", value="\n".join(lines), inline=False))
    if audit.write_back_active:
        lines = [
            f"• {r.subject} → {r.object} ({', '.join(r.kind_filter) or 'advice.*'})"
            for r in audit.write_back_active[:8]
        ]
        fields.append(EmbedField(name="write_back actifs", value="\n".join(lines), inline=False))
    title_status = color_title(audit.alert_color, green=GREEN, yellow=YELLOW, red=YELLOW)
    return Embed(
        title=f"CapabilityRouter — {title_status}",
        description=audit.summary,
        color=audit.alert_color,
        fields=fields,
        footer="Argos Ops • CapabilityRouter",
    )


class CapabilityRouter(BaseAgent):
    """Capability Manager — audite le câblage inter-agents (read-only)."""

    name = "CapabilityRouter"
    command = "/run-capability-router"
    breaker_name = None
    ai_act_risk_class = "minimal"

    def __init__(
        self,
        *,
        capabilities_path: Path = DEFAULT_CAPABILITIES_PATH,
        memory_root: Path = fleet_memory.FLEET_MEMORY_DIR,
    ) -> None:
        self._capabilities_path = capabilities_path
        self._memory_root = memory_root

    async def run(self) -> RunResult:
        audit = await audit_capabilities(
            capabilities_path=self._capabilities_path, memory_root=self._memory_root
        )
        logger.info(f"CapabilityRouter — {audit.summary}")
        inputs = [
            IOItem(
                label="Câblage inter-agents",
                kind="file",
                detail=f"{audit.total_rules} règle(s) déclarée(s)",
                ref="data/agent_capabilities.yaml",
                count=audit.total_rules,
            )
        ]
        outputs = [
            IOItem(
                label="Anomalies de câblage",
                kind="memory",
                detail=audit.summary,
                count=len(audit.orphan_rules) + len(audit.empty_wirings),
            )
        ]
        return await emit_alert_or_silence(
            audit,
            embed_builder=build_capability_embed,
            agent_name=self.name,
            inputs=inputs,
            outputs=outputs,
        )


__all__ = [
    "CapabilityAudit",
    "CapabilityRouter",
    "audit_capabilities",
    "build_capability_embed",
]
