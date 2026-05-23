"""Entrée CLI du CompetitorWatcher — invoquée par cron / Task Scheduler.

Usage::

    uv run python scripts/run_competitor_watcher.py

Cf. :mod:`argos_ops.agents.competitor_watcher`. Politique : silence si
pages stables (cache 24 h + hash comparison) ; embed jaune sinon.

Réseau requis : fetch HTTP des URLs listées dans
``data/competitors/targets.yaml``.
"""

from __future__ import annotations

import asyncio
import sys

from loguru import logger

from argos_ops.agents.base import run_agent
from argos_ops.agents.competitor_watcher import CompetitorWatcher
from argos_ops.crm.db import dispose_engine


async def amain() -> int:
    try:
        result = await run_agent(CompetitorWatcher())
    finally:
        await dispose_engine()

    if result.status == "success":
        logger.success(f"CompetitorWatcher OK — {result.output_summary}")
        return 0
    logger.error(f"CompetitorWatcher {result.status} — {result.error}")
    return 1


def main() -> int:
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    return asyncio.run(amain())


if __name__ == "__main__":
    sys.exit(main())
