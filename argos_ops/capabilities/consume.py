"""API runtime des capabilities : ``consume_capabilities`` + ``write_back``.

Côté **agent consommateur** (au début de son ``run()``) ::

    from argos_ops.capabilities import consume_capabilities
    context = await consume_capabilities("OutboundBot")
    # context = {"EmailBot": [<Fact lead-signal inbound>, ...], ...}

Côté **agent qui conseille** ::

    from argos_ops.capabilities import write_back
    await write_back("BudgetWatcher", "AdBot", "budget_adjust",
                     "Cap conseillé 30€/j (MRR -8% S20)")
    # -> fait kind='advice.budget_adjust' dans la mémoire d'AdBot,
    #    qu'AdBot lira via sa propre capability read. CapabilityDeniedError
    #    si aucune règle write_back enabled n'existe.

File-based (D-033) : ``read`` réutilise ``fleet_memory.read_memory`` +
le graphe d'accès ; ``write_back`` écrit un fait ``advice.*`` idempotent.
"""

from __future__ import annotations

from pathlib import Path

from loguru import logger

from argos_ops import fleet_memory
from argos_ops.capabilities.loader import (
    DEFAULT_CAPABILITIES_PATH,
    effective_read_rules,
    find_write_back_rule,
    load_capabilities,
)
from argos_ops.capabilities.models import WRITE_BACK_KIND_PREFIX
from argos_ops.exceptions import CapabilityDeniedError
from argos_ops.fleet_memory import Fact

# Fenêtre de fraîcheur : un consommateur ne tire que les faits récents.
DEFAULT_WRITE_BACK_TTL_DAYS = 30


async def consume_capabilities(
    agent_name: str,
    *,
    capabilities_path: Path = DEFAULT_CAPABILITIES_PATH,
    memory_root: Path = fleet_memory.FLEET_MEMORY_DIR,
) -> dict[str, list[Fact]]:
    """Tire les faits actifs que ``agent_name`` a le droit de consommer.

    Retourne ``{object_agent: [Fact, ...]}`` filtré par les règles (kind /
    tags / enabled) au-dessus du graphe d'accès. Dict vide si l'agent ne
    lit personne. Ne lève jamais : une erreur de lecture d'un object est
    loguée et l'object est sauté (best-effort, comme la mémoire).
    """
    rules = load_capabilities(capabilities_path)
    access_graph = await fleet_memory.load_access_graph(root=memory_root)
    allowed = effective_read_rules(agent_name, rules, access_graph)

    out: dict[str, list[Fact]] = {}
    for obj, rule in allowed.items():
        if obj == agent_name:
            continue
        try:
            mem = await fleet_memory.read_memory(obj, root=memory_root)
        except Exception as exc:  # un object illisible ne casse pas le tirage
            logger.warning(f"capabilities: lecture {obj} échouée pour {agent_name} : {exc}")
            continue
        facts = [
            f
            for f in mem.active_facts
            if rule is None or rule.matches_fact(kind=f.kind, tags=f.tags)
        ]
        if facts:
            out[obj] = facts
    return out


async def write_back(
    from_agent: str,
    to_agent: str,
    advice_type: str,
    body: str,
    *,
    capabilities_path: Path = DEFAULT_CAPABILITIES_PATH,
    memory_root: Path = fleet_memory.FLEET_MEMORY_DIR,
) -> Fact:
    """Dépose un conseil ``advice.<type>`` dans la mémoire de ``to_agent``.

    Exige une règle ``write_back enabled=true`` ``from_agent`` → ``to_agent``,
    sinon :class:`CapabilityDeniedError` (write_back est DENY par défaut — risque
    comportemental). Le fait est idempotent (kind ``advice.<type>``, source
    ``<from_agent> (write_back)``), lu par ``to_agent`` à son prochain run.
    """
    if not body.strip():
        raise ValueError("write_back: body vide interdit")
    rules = load_capabilities(capabilities_path)
    if find_write_back_rule(from_agent, to_agent, rules) is None:
        raise CapabilityDeniedError(
            f"write_back refusé : aucune capability enabled {from_agent} → {to_agent}. "
            "Ajoute une règle write_back enabled=true dans data/agent_capabilities.yaml."
        )
    kind = f"{WRITE_BACK_KIND_PREFIX}{advice_type}"
    fact = await fleet_memory.append_fact(
        to_agent,
        body,
        kind=kind,
        source=f"{from_agent} (write_back)",
        confidence="medium",
        tags=("advice",),
        ttl_days=DEFAULT_WRITE_BACK_TTL_DAYS,
        root=memory_root,
    )
    logger.info(f"capabilities: write_back {from_agent} → {to_agent} ({kind})")
    return fact


__all__ = ["DEFAULT_WRITE_BACK_TTL_DAYS", "consume_capabilities", "write_back"]
