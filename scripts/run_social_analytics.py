"""Entrée CLI SocialAnalytics — engagement 7j par canal (P22.I).

Usage::

    uv run python scripts/run_social_analytics.py
"""

from __future__ import annotations

import asyncio
import sys

from loguru import logger

from argos_ops.agents.base import run_agent
from argos_ops.agents.social_analytics import SocialAnalytics
from argos_ops.crm.db import dispose_engine


async def amain() -> int:
    try:
        result = await run_agent(SocialAnalytics())
    finally:
        await dispose_engine()
    if result.status == "success":
        logger.success(f"SocialAnalytics OK — {result.output_summary}")
        return 0
    logger.error(f"SocialAnalytics {result.status} — {result.error}")
    return 1


def main() -> int:
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    return asyncio.run(amain())


if __name__ == "__main__":
    sys.exit(main())
