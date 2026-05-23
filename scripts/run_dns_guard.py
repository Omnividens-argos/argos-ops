"""Entrée CLI du DNSGuard — invoquée par cron / Task Scheduler.

Usage::

    uv run python scripts/run_dns_guard.py

Cf. :mod:`argos_ops.agents.dns_guard`. Politique : silence si la zone
``omnividens.fr`` est inchangée vs snapshot précédent ; embed jaune si
TXT/sous-domaine bouge ; rouge si A root ou MX changent.
"""

from __future__ import annotations

import asyncio
import sys

from loguru import logger

from argos_ops.agents.base import run_agent
from argos_ops.agents.dns_guard import DNSGuard
from argos_ops.crm.db import dispose_engine


async def amain() -> int:
    try:
        result = await run_agent(DNSGuard())
    finally:
        await dispose_engine()

    if result.status == "success":
        logger.success(f"DNSGuard OK — {result.output_summary}")
        return 0
    logger.error(f"DNSGuard {result.status} — {result.error}")
    return 1


def main() -> int:
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    return asyncio.run(amain())


if __name__ == "__main__":
    sys.exit(main())
