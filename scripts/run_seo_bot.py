"""Entrée CLI SEOBot — health-check passif (P22.I).

Usage::

    uv run python scripts/run_seo_bot.py

Le drafting réel des briefs SEO passe par le slash
``/generate-seo-brief`` (humain-in-the-loop). Ce script vérifie juste
combien de briefs sont déjà présents sous ``data/seo/briefs/``.
"""

from __future__ import annotations

import asyncio
import sys

from loguru import logger

from argos_ops.agents.base import run_agent
from argos_ops.agents.seo_bot import SEOBot
from argos_ops.crm.db import dispose_engine


async def amain() -> int:
    try:
        result = await run_agent(SEOBot())
    finally:
        await dispose_engine()
    if result.status == "success":
        logger.success(f"SEOBot OK — {result.output_summary}")
        return 0
    logger.error(f"SEOBot {result.status} — {result.error}")
    return 1


def main() -> int:
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    return asyncio.run(amain())


if __name__ == "__main__":
    sys.exit(main())
