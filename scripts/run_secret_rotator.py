"""Entrée CLI du SecretRotator — invoquée par cron / Task Scheduler.

Usage::

    uv run python scripts/run_secret_rotator.py

Cf. :mod:`argos_ops.agents.secret_rotator`. Politique : silence si tous
les secrets rotés < 90j, embed jaune si due (90-180j), rouge si > 180j.
"""

from __future__ import annotations

import asyncio
import sys

from loguru import logger

from argos_ops.agents.base import run_agent
from argos_ops.agents.secret_rotator import SecretRotator
from argos_ops.crm.db import dispose_engine


async def amain() -> int:
    try:
        result = await run_agent(SecretRotator())
    finally:
        await dispose_engine()

    if result.status == "success":
        logger.success(f"SecretRotator OK — {result.output_summary}")
        return 0
    logger.error(f"SecretRotator {result.status} — {result.error}")
    return 1


def main() -> int:
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    return asyncio.run(amain())


if __name__ == "__main__":
    sys.exit(main())
