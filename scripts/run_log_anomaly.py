"""Entrée CLI du LogAnomalyDetector — invoquée par cron / Task Scheduler.

Usage::

    uv run python scripts/run_log_anomaly.py

Cf. :mod:`argos_ops.agents.log_anomaly`. Politique : silence si volume
horaire normal ; embed jaune si ratio current/baseline ≥3x ; rouge si
≥5x ou ≥50 erreurs/h en absolu.
"""

from __future__ import annotations

import asyncio
import sys

from loguru import logger

from argos_ops.agents.base import run_agent
from argos_ops.agents.log_anomaly import LogAnomalyDetector
from argos_ops.crm.db import dispose_engine


async def amain() -> int:
    try:
        result = await run_agent(LogAnomalyDetector())
    finally:
        await dispose_engine()

    if result.status == "success":
        logger.success(f"LogAnomalyDetector OK — {result.output_summary}")
        return 0
    logger.error(f"LogAnomalyDetector {result.status} — {result.error}")
    return 1


def main() -> int:
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    return asyncio.run(amain())


if __name__ == "__main__":
    sys.exit(main())
