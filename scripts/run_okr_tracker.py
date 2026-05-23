"""Entrée CLI du OKRTracker.

Usage::

    uv run python scripts/run_okr_tracker.py
"""

from __future__ import annotations

import asyncio
import sys

from loguru import logger

from argos_ops.agents.base import run_agent
from argos_ops.agents.okr_tracker import OKRTracker
from argos_ops.crm.db import dispose_engine


async def amain() -> int:
    try:
        result = await run_agent(OKRTracker())
    finally:
        await dispose_engine()

    if result.status == "success":
        logger.success(f"OKRTracker OK — {result.output_summary}")
        return 0
    logger.error(f"OKRTracker {result.status} — {result.error}")
    return 1


def main() -> int:
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    return asyncio.run(amain())


if __name__ == "__main__":
    sys.exit(main())
