"""Entrée CLI EditorialBot — digest TrendSpotter → queue de recommandations.

Usage::

    uv run python scripts/run_editorial.py

Lit le dernier ``data/trends/digest-<date>.md`` et écrit
``data/editorial/queue-<date>.yaml`` (recommandations writer/canal/angle).
Ne lance aucun writer — le fondateur exécute ensuite les ``/draft-*`` listés.
"""

from __future__ import annotations

import asyncio
import sys

from loguru import logger

from argos_ops.agents.base import run_agent
from argos_ops.agents.editorial_bot import EditorialBot
from argos_ops.crm.db import dispose_engine


async def amain() -> int:
    try:
        result = await run_agent(EditorialBot())
    finally:
        await dispose_engine()
    if result.status == "success":
        logger.success(f"EditorialBot OK — {result.output_summary}")
        return 0
    logger.error(f"EditorialBot {result.status} — {result.error}")
    return 1


def main() -> int:
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    return asyncio.run(amain())


if __name__ == "__main__":
    sys.exit(main())
