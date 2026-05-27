"""Entrée CLI SupportBot — health-check passif KB (P22.G).

Usage::

    uv run python scripts/run_support_bot.py

Le RAG Tier 1 interactif passe par le slash ``/run-support-tier1``
(humain-in-the-loop + skill kb-rag). Ce script vérifie juste que la KB
est seedée pour que SupportBot puisse répondre.
"""

from __future__ import annotations

import asyncio
import sys

from loguru import logger

from argos_ops.agents.base import run_agent
from argos_ops.agents.support_bot import SupportBot
from argos_ops.crm.db import dispose_engine


async def amain() -> int:
    try:
        result = await run_agent(SupportBot())
    finally:
        await dispose_engine()
    if result.status == "success":
        logger.success(f"SupportBot OK — {result.output_summary}")
        return 0
    logger.error(f"SupportBot {result.status} — {result.error}")
    return 1


def main() -> int:
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    return asyncio.run(amain())


if __name__ == "__main__":
    sys.exit(main())
