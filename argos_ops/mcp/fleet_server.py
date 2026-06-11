"""Serveur MCP « argos-fleet » — pilotage de la flotte pour l'Atelier libre.

Expose à Claude (mode **pilotage flotte**) des outils typés pour :
- **lire** la mémoire des bots (faits conservés + le « IN » résolu par graphe) ;
- **écrire** un fait en mémoire (capitaliser ce que l'atelier apprend) ;
- **lancer** un bot et récupérer son résultat.

Aucun bash, aucune édition du repo. Les bots qui publient/envoient
s'auto-protègent par leurs propres flags shadow/live (D-024/025/026, OUTBOUND…) :
l'atelier ne peut déclencher une action externe que si le flag live est déjà ON.

Transport : stdio (lancé par le CLI ``claude`` via ``--mcp-config``). Démarré
en sous-process à chaque tour de l'atelier ; cf. ``ops_dashboard/atelier.py``.

⚠️ Windows : ``run_bot`` exécute l'agent dans un **event loop dédié**
(``SelectorEventLoop``, requis par psycopg) isolé de la boucle stdio du serveur
MCP — même logique que le fix subprocess de l'atelier.
"""

from __future__ import annotations

import asyncio
import sys
from typing import Any

import anyio
from mcp.server.fastmcp import FastMCP

from argos_ops.agents.base import RunResult, run_agent
from argos_ops.fleet_memory import (
    DEFAULT_FACT_TTL_DAYS,
    Confidence,
    Fact,
    append_fact,
    read_memory,
    visible_memory,
)
from argos_ops.fleet_memory import list_bots as fm_list_bots
from argos_ops.ops_dashboard.app import KNOWN_AGENTS, RUNNABLE_AGENTS, _build_agent

mcp = FastMCP("argos-fleet")


def _fact_dict(fact: Fact) -> dict[str, Any]:
    return {
        "id": fact.id,
        "kind": fact.kind,
        "body": fact.body,
        "confidence": fact.confidence,
        "status": fact.status,
        "tags": list(fact.tags),
        "ttl_days": fact.ttl_days,
        "pinned": fact.pinned,
        "created_at": fact.created_at.isoformat(),
    }


def _run_bot_blocking(name: str) -> RunResult:
    """Exécute l'agent dans un event loop dédié (Selector sur Windows pour psycopg)."""
    loop = asyncio.SelectorEventLoop() if sys.platform == "win32" else asyncio.new_event_loop()
    try:
        return loop.run_until_complete(run_agent(_build_agent(name)))
    finally:
        loop.close()


@mcp.tool()
async def list_bots() -> dict[str, Any]:
    """Liste les bots de la flotte.

    - ``runnable`` : bots lançables via :func:`run_bot`.
    - ``all`` : tous les bots connus du panel.
    - ``with_memory`` : bots qui ont déjà une mémoire (faits conservés).
    """
    return {
        "runnable": sorted(RUNNABLE_AGENTS),
        "all": sorted(KNOWN_AGENTS),
        "with_memory": fm_list_bots(),
    }


@mcp.tool()
async def run_bot(name: str) -> dict[str, Any]:
    """Lance un bot et retourne son résultat.

    Respecte les garde-fous runtime (breaker tripped / désactivé / pause /
    quota journalier) et les flags shadow/live propres au bot. Retourne
    ``{status, output_summary, error}``.
    """
    if name not in RUNNABLE_AGENTS:
        return {
            "status": "error",
            "error": f"Bot non lançable : {name}. Utilise list_bots() pour les noms valides.",
        }
    result: RunResult = await anyio.to_thread.run_sync(_run_bot_blocking, name)
    return {
        "status": result.status,
        "output_summary": result.output_summary,
        "error": result.error,
    }


@mcp.tool()
async def read_bot_memory(name: str, include_archived: bool = False) -> dict[str, Any]:
    """Lit la mémoire propre d'un bot (faits qu'il a conservés)."""
    mem = await read_memory(name, include_archived=include_archived)
    return {"bot": name, "facts": [_fact_dict(f) for f in mem.facts]}


@mcp.tool()
async def bot_in_memory(name: str) -> dict[str, Any]:
    """« IN mémoire » d'un bot : sa mémoire + celle des bots qu'il a le droit de lire.

    Respecte le graphe d'accès (un bot ne voit que ce qui lui est utile).
    """
    vis = await visible_memory(name)
    return {bot: [_fact_dict(f) for f in mem.facts] for bot, mem in vis.items()}


@mcp.tool()
async def remember_fact(
    bot: str,
    body: str,
    kind: str = "note",
    confidence: Confidence = "medium",
    tags: list[str] | None = None,
    ttl_days: int | None = DEFAULT_FACT_TTL_DAYS,
    pinned: bool = False,
) -> dict[str, Any]:
    """Conserve un fait dans la mémoire d'un bot (capitaliser ce que tu apprends).

    Idempotent par corps (même contenu = même fact_id, pas de doublon).
    ``ttl_days`` défaut 180 j ; passe ``pinned=true`` seulement pour un fait
    durable validé avec le fondateur. Le bot doit être connu de la flotte.
    """
    if bot not in KNOWN_AGENTS:
        return {
            "status": "error",
            "error": f"Bot inconnu : {bot}. Utilise list_bots() pour les noms valides.",
        }
    if not body.strip():
        return {"status": "error", "error": "body vide"}
    fact = await append_fact(
        bot,
        body,
        kind=kind,
        source="atelier",
        confidence=confidence,
        tags=tuple(tags or ()),
        ttl_days=ttl_days,
        pinned=pinned,
    )
    return {"status": "ok", "fact": _fact_dict(fact)}


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
