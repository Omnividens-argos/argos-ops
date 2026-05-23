"""Entrée CLI du ErrorTriageBot — invoquée par cron / Task Scheduler.

Usage::

    uv run python scripts/run_error_triage.py

Cf. :mod:`argos_ops.agents.error_triage`. Politique : silence si aucun
cluster ne dépasse 3 occurrences, embed sinon (jaune <10, rouge >=10).
"""

from __future__ import annotations

import asyncio
import sys

from loguru import logger

from argos_ops.agents.base import run_agent
from argos_ops.agents.error_triage import ErrorTriageBot
from argos_ops.crm.db import dispose_engine


async def amain() -> int:
    try:
        result = await run_agent(ErrorTriageBot())
    finally:
        await dispose_engine()

    if result.status == "success":
        logger.success(f"ErrorTriageBot OK — {result.output_summary}")
        return 0
    logger.error(f"ErrorTriageBot {result.status} — {result.error}")
    return 1


def main() -> int:
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    return asyncio.run(amain())


if __name__ == "__main__":
    sys.exit(main())
