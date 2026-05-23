"""Entrée CLI du DiagramGenerator (P22.F Sprint 13).

Usage::

    uv run python scripts/run_diagram_generator.py <slug>
"""

from __future__ import annotations

import asyncio
import sys

from loguru import logger

from argos_ops.agents.base import run_agent
from argos_ops.agents.diagram_generator import DiagramGenerator
from argos_ops.crm.db import dispose_engine


async def amain(slug: str) -> int:
    try:
        result = await run_agent(DiagramGenerator(slug))
    finally:
        await dispose_engine()
    if result.status == "success":
        logger.success(f"DiagramGenerator OK — {result.output_summary}")
        return 0
    logger.error(f"DiagramGenerator {result.status} — {result.error}")
    return 1


def main() -> int:
    if len(sys.argv) < 2:
        logger.error("Usage: run_diagram_generator.py <slug>")
        return 2
    slug = sys.argv[1]
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    return asyncio.run(amain(slug))


if __name__ == "__main__":
    sys.exit(main())
