"""Entrée CLI du UptimeMonitor — invoquée par cron / Task Scheduler.

Usage::

    uv run python scripts/run_uptime_monitor.py

Cf. :mod:`argos_ops.agents.uptime_monitor`. Politique : silence si tous
les endpoints sont 2xx/3xx, embed jaune si 4xx, rouge si down/timeout.
"""

from __future__ import annotations

import asyncio
import sys

from loguru import logger

from argos_ops.agents.base import run_agent
from argos_ops.agents.uptime_monitor import UptimeMonitor
from argos_ops.crm.db import dispose_engine


async def amain() -> int:
    try:
        result = await run_agent(UptimeMonitor())
    finally:
        await dispose_engine()

    if result.status == "success":
        logger.success(f"UptimeMonitor OK — {result.output_summary}")
        return 0
    logger.error(f"UptimeMonitor {result.status} — {result.error}")
    return 1


def main() -> int:
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    return asyncio.run(amain())


if __name__ == "__main__":
    sys.exit(main())
