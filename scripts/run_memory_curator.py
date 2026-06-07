"""Entrée CLI du MemoryCurator — invoquée par cron / Task Scheduler.

Usage::

    uv run python scripts/run_memory_curator.py

Cf. :mod:`argos_ops.agents.memory_curator`. Nettoie la mémoire de flotte :
archive le périmé (TTL) + le stale, purge le très vieux déjà archivé, protège
les faits ``pinned``. Silence Discord si rien n'a bougé.
"""

from __future__ import annotations

import asyncio
import sys

from loguru import logger

from argos_ops.agents.base import run_agent
from argos_ops.agents.memory_curator import MemoryCurator
from argos_ops.crm.db import dispose_engine


async def amain() -> int:
    try:
        result = await run_agent(MemoryCurator())
    finally:
        await dispose_engine()

    if result.status == "success":
        logger.success(f"MemoryCurator OK — {result.output_summary}")
        return 0
    logger.error(f"MemoryCurator {result.status} — {result.error}")
    return 1


def main() -> int:
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    return asyncio.run(amain())


if __name__ == "__main__":
    sys.exit(main())
