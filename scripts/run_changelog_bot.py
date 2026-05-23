"""Entrée CLI ChangelogBot (P22.G Produit Sprint 11).

Usage : ``uv run python scripts/run_changelog_bot.py [from_ref] [to_ref]``

Sans arg : prend le tag le plus récent comme base, HEAD comme tip.
"""

from __future__ import annotations

import asyncio
import sys

from loguru import logger

from argos_ops.agents.base import run_agent
from argos_ops.agents.changelog_bot import ChangelogBot
from argos_ops.crm.db import dispose_engine


async def amain(argv: list[str]) -> int:
    from_ref = argv[1] if len(argv) > 1 else None
    to_ref = argv[2] if len(argv) > 2 else "HEAD"
    try:
        result = await run_agent(ChangelogBot(from_ref=from_ref, to_ref=to_ref))
    finally:
        await dispose_engine()
    if result.status == "success":
        logger.success(f"ChangelogBot OK — {result.output_summary}")
        return 0
    logger.error(f"ChangelogBot {result.status} — {result.error}")
    return 1


def main() -> int:
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    return asyncio.run(amain(sys.argv))


if __name__ == "__main__":
    sys.exit(main())
