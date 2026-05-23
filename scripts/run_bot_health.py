"""Entrée CLI du BotHealthBot — invoquée par cron / Task Scheduler.

Usage::

    uv run python scripts/run_bot_health.py

Sortie : 0 si success (qu'il y ait alerte Discord ou non), 1 si
failed / killed_by_breaker. Tous les détails (snapshots par agent,
décision d'alerte, erreur éventuelle) sont loggés via loguru et
persistés dans ``agent_runs``.

Politique : silence Discord si tout vert, embed sinon. Cf.
:mod:`argos_ops.agents.bot_health`.
"""

from __future__ import annotations

import asyncio
import sys

from loguru import logger

from argos_ops.agents.base import run_agent
from argos_ops.agents.bot_health import BotHealthBot
from argos_ops.crm.db import dispose_engine


async def amain() -> int:
    try:
        result = await run_agent(BotHealthBot())
    finally:
        await dispose_engine()

    if result.status == "success":
        logger.success(f"BotHealthBot OK — {result.output_summary}")
        return 0
    logger.error(f"BotHealthBot {result.status} — {result.error}")
    return 1


def main() -> int:
    # psycopg async exige SelectorEventLoop sur Windows.
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    return asyncio.run(amain())


if __name__ == "__main__":
    sys.exit(main())
