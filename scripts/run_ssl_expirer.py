"""Entrée CLI du SSLExpirer — invoquée par cron / Task Scheduler.

Usage::

    uv run python scripts/run_ssl_expirer.py

Cf. :mod:`argos_ops.agents.ssl_expirer`. Politique : silence si tous
les certs > 30j, embed jaune si <30j, rouge si <7j ou expiré.
"""

from __future__ import annotations

import asyncio
import sys

from loguru import logger

from argos_ops.agents.base import run_agent
from argos_ops.agents.ssl_expirer import SSLExpirer
from argos_ops.crm.db import dispose_engine


async def amain() -> int:
    try:
        result = await run_agent(SSLExpirer())
    finally:
        await dispose_engine()

    if result.status == "success":
        logger.success(f"SSLExpirer OK — {result.output_summary}")
        return 0
    logger.error(f"SSLExpirer {result.status} — {result.error}")
    return 1


def main() -> int:
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    return asyncio.run(amain())


if __name__ == "__main__":
    sys.exit(main())
