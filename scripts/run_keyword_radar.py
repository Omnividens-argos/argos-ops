"""Entrée CLI KeywordRadar — SERP movements (P22.I).

Usage::

    uv run python scripts/run_keyword_radar.py
"""

from __future__ import annotations

import asyncio
import sys

from loguru import logger

from argos_ops.agents.base import run_agent
from argos_ops.agents.keyword_radar import KeywordRadar
from argos_ops.crm.db import dispose_engine


async def amain() -> int:
    try:
        result = await run_agent(KeywordRadar())
    finally:
        await dispose_engine()
    if result.status == "success":
        logger.success(f"KeywordRadar OK — {result.output_summary}")
        return 0
    logger.error(f"KeywordRadar {result.status} — {result.error}")
    return 1


def main() -> int:
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    return asyncio.run(amain())


if __name__ == "__main__":
    sys.exit(main())
