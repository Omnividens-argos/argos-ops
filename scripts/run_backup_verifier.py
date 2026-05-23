"""Entrée CLI du BackupVerifier — invoquée par cron / Task Scheduler.

Usage::

    uv run python scripts/run_backup_verifier.py

Cf. :mod:`argos_ops.agents.backup_verifier`. Politique : silence si le
dernier backup date de < 24h, embed jaune si 24-72h, rouge si > 72h
ou absent.
"""

from __future__ import annotations

import asyncio
import sys

from loguru import logger

from argos_ops.agents.backup_verifier import BackupVerifier
from argos_ops.agents.base import run_agent
from argos_ops.crm.db import dispose_engine


async def amain() -> int:
    try:
        result = await run_agent(BackupVerifier())
    finally:
        await dispose_engine()

    if result.status == "success":
        logger.success(f"BackupVerifier OK — {result.output_summary}")
        return 0
    logger.error(f"BackupVerifier {result.status} — {result.error}")
    return 1


def main() -> int:
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    return asyncio.run(amain())


if __name__ == "__main__":
    sys.exit(main())
