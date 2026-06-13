"""Entrée CLI du FleetWatchdog — invoquée par cron / Task Scheduler.

Usage::

    uv run python scripts/run_fleet_watchdog.py

SRE unifié de la flotte (Axe 3.2) : fusionne santé/freshness + perf +
triage erreurs + anomalie de volume en une seule passe sur ``agent_runs``,
1 embed Discord multi-sections, silence si les 4 sections sont vertes.

Sortie : 0 si success (qu'il y ait alerte Discord ou non), 1 si
failed / killed_by_breaker. Détails loggés via loguru et persistés dans
``agent_runs``. Cf. :mod:`argos_ops.agents.fleet_watchdog`.
"""

from __future__ import annotations

import asyncio
import sys

from loguru import logger

from argos_ops.agents.base import run_agent
from argos_ops.agents.fleet_watchdog import FleetWatchdog
from argos_ops.crm.db import dispose_engine


async def amain() -> int:
    try:
        result = await run_agent(FleetWatchdog())
    finally:
        await dispose_engine()

    if result.status == "success":
        logger.success(f"FleetWatchdog OK — {result.output_summary}")
        return 0
    logger.error(f"FleetWatchdog {result.status} — {result.error}")
    return 1


def main() -> int:
    # psycopg async exige SelectorEventLoop sur Windows.
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    return asyncio.run(amain())


if __name__ == "__main__":
    sys.exit(main())
