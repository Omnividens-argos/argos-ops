"""Entrée CLI du KillSwitchOperator — invoquée par cron / Task Scheduler.

Usage::

    uv run python scripts/run_kill_switch.py

Cf. :mod:`argos_ops.agents.kill_switch`. Politique : alerte 1x/jour
pour chaque breaker tripped depuis > 4h (déduplication via lecture
des agent_runs récents).
"""

from __future__ import annotations

import asyncio
import sys

from loguru import logger

from argos_ops.agents.base import run_agent
from argos_ops.agents.kill_switch import KillSwitchOperator
from argos_ops.crm.db import dispose_engine


async def amain() -> int:
    try:
        result = await run_agent(KillSwitchOperator())
    finally:
        await dispose_engine()

    if result.status == "success":
        logger.success(f"KillSwitchOperator OK — {result.output_summary}")
        return 0
    logger.error(f"KillSwitchOperator {result.status} — {result.error}")
    return 1


def main() -> int:
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    return asyncio.run(amain())


if __name__ == "__main__":
    sys.exit(main())
