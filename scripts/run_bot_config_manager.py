"""Entrée CLI du BotConfigManager — invoquée par cron / Task Scheduler.

Usage::

    uv run python scripts/run_bot_config_manager.py

Cf. :mod:`argos_ops.agents.bot_config_manager`. Politique : silence
si aucun drift entre baseline.yaml et agent_config DB, embed sinon.
"""

from __future__ import annotations

import asyncio
import sys

from loguru import logger

from argos_ops.agents.base import run_agent
from argos_ops.agents.bot_config_manager import BotConfigManager
from argos_ops.crm.db import dispose_engine


async def amain() -> int:
    try:
        result = await run_agent(BotConfigManager())
    finally:
        await dispose_engine()

    if result.status == "success":
        logger.success(f"BotConfigManager OK — {result.output_summary}")
        return 0
    logger.error(f"BotConfigManager {result.status} — {result.error}")
    return 1


def main() -> int:
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    return asyncio.run(amain())


if __name__ == "__main__":
    sys.exit(main())
