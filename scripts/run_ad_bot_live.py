"""Entrée CLI AdBot live — apply ads recos (P22.I).

Usage::

    uv run python scripts/run_ad_bot_live.py

Shadow par défaut. Live uniquement si ADS_LIVE_MODE=true et
ADS_DAILY_BUDGET_EUR > 0 dans .env.local.
"""

from __future__ import annotations

import asyncio
import sys

from loguru import logger

from argos_ops.agents.ad_bot_live import AdBotLive
from argos_ops.agents.base import run_agent
from argos_ops.crm.db import dispose_engine


async def amain() -> int:
    try:
        result = await run_agent(AdBotLive())
    finally:
        await dispose_engine()
    if result.status == "success":
        logger.success(f"AdBot OK — {result.output_summary}")
        return 0
    logger.error(f"AdBot {result.status} — {result.error}")
    return 1


def main() -> int:
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    return asyncio.run(amain())


if __name__ == "__main__":
    sys.exit(main())
