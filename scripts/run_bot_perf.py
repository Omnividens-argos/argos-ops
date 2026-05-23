"""Entrée CLI du BotPerfAnalyzer — invoquée par cron / Task Scheduler.

Usage::

    uv run python scripts/run_bot_perf.py

Cf. :mod:`argos_ops.agents.bot_perf_analyzer`. Politique : silence
Discord si pas de régression, embed sinon.
"""

from __future__ import annotations

import asyncio
import sys

from loguru import logger

from argos_ops.agents.base import run_agent
from argos_ops.agents.bot_perf_analyzer import BotPerfAnalyzer
from argos_ops.crm.db import dispose_engine


async def amain() -> int:
    try:
        result = await run_agent(BotPerfAnalyzer())
    finally:
        await dispose_engine()

    if result.status == "success":
        logger.success(f"BotPerfAnalyzer OK — {result.output_summary}")
        return 0
    logger.error(f"BotPerfAnalyzer {result.status} — {result.error}")
    return 1


def main() -> int:
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    return asyncio.run(amain())


if __name__ == "__main__":
    sys.exit(main())
