"""Entrée CLI ContentBot — publie drafts validés sur LinkedIn/Mastodon (P22.I).

Usage::

    uv run python scripts/run_content_bot.py
"""

from __future__ import annotations

import asyncio
import sys

from loguru import logger

from argos_ops.agents.base import run_agent
from argos_ops.agents.content_bot import ContentBot
from argos_ops.crm.db import dispose_engine


async def amain() -> int:
    try:
        result = await run_agent(ContentBot())
    finally:
        await dispose_engine()
    if result.status == "success":
        logger.success(f"ContentBot OK — {result.output_summary}")
        return 0
    logger.error(f"ContentBot {result.status} — {result.error}")
    return 1


def main() -> int:
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    return asyncio.run(amain())


if __name__ == "__main__":
    sys.exit(main())
