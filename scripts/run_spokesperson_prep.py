"""Entrée CLI SpokespersonPrep — brief Q&A avant interview (P22.L).

Usage::

    uv run python scripts/run_spokesperson_prep.py
"""

from __future__ import annotations

import asyncio
import sys

from loguru import logger

from argos_ops.agents.base import run_agent
from argos_ops.agents.spokesperson_prep import SpokespersonPrep
from argos_ops.crm.db import dispose_engine


async def amain() -> int:
    try:
        result = await run_agent(SpokespersonPrep())
    finally:
        await dispose_engine()
    if result.status == "success":
        logger.success(f"SpokespersonPrep OK — {result.output_summary}")
        return 0
    logger.error(f"SpokespersonPrep {result.status} — {result.error}")
    return 1


def main() -> int:
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    return asyncio.run(amain())


if __name__ == "__main__":
    sys.exit(main())
