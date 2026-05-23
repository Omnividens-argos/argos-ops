"""Entrée CLI de l'OrchestratorBot.

Usage::

    uv run python scripts/run_orchestrator.py             # dry-run (défaut)
    uv run python scripts/run_orchestrator.py --live      # exécute
    uv run python scripts/run_orchestrator.py --max-concurrent 3

Sortie : 0 si success, 1 si failed / killed_by_breaker. Le plan
complet (decision par agent, raison) est loggé via loguru et
persisté dans ``agent_runs.output_summary``.

Mode dry-run **par défaut** — refuse de lancer quoi que ce soit
tant que ``--live`` n'est pas passé explicitement. C'est le garde-fou
le plus simple contre un cron malencontreux qui lancerait des
agents en boucle.
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from loguru import logger

from argos_ops.agents.base import run_agent
from argos_ops.agents.orchestrator import DEFAULT_MAX_CONCURRENT, OrchestratorBot
from argos_ops.crm.db import dispose_engine


async def amain(*, live: bool, max_concurrent: int) -> int:
    try:
        result = await run_agent(OrchestratorBot(live=live, max_concurrent=max_concurrent))
    finally:
        await dispose_engine()

    if result.status == "success":
        logger.success(f"OrchestratorBot OK — {result.output_summary}")
        return 0
    logger.error(f"OrchestratorBot {result.status} — {result.error}")
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(description="OrchestratorBot — chef de fleet Argos Ops")
    parser.add_argument(
        "--live",
        action="store_true",
        help="Mode live : déclenche réellement les agents (défaut = dry-run)",
    )
    parser.add_argument(
        "--max-concurrent",
        type=int,
        default=DEFAULT_MAX_CONCURRENT,
        help=f"Nombre max d'agents lancés en parallèle (default {DEFAULT_MAX_CONCURRENT})",
    )
    args = parser.parse_args()

    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    return asyncio.run(amain(live=args.live, max_concurrent=args.max_concurrent))


if __name__ == "__main__":
    sys.exit(main())
