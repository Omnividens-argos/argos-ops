"""Entrée CLI du CapabilityRouter — invoquée par cron / Task Scheduler.

Usage::

    uv run python scripts/run_capability_router.py

Cf. :mod:`argos_ops.agents.capability_router`. Audite le câblage inter-agents
(``data/agent_capabilities.yaml`` + graphe d'accès) et alerte sur les anomalies
(règles orphelines, câblages à vide, write_back actifs). Silence si sain.
"""

from __future__ import annotations

import asyncio
import sys

from loguru import logger

from argos_ops.agents.base import run_agent
from argos_ops.agents.capability_router import CapabilityRouter
from argos_ops.crm.db import dispose_engine


async def amain() -> int:
    try:
        result = await run_agent(CapabilityRouter())
    finally:
        await dispose_engine()

    if result.status == "success":
        logger.success(f"CapabilityRouter OK — {result.output_summary}")
        return 0
    logger.error(f"CapabilityRouter {result.status} — {result.error}")
    return 1


def main() -> int:
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    return asyncio.run(amain())


if __name__ == "__main__":
    sys.exit(main())
