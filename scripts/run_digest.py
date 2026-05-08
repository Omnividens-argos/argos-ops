"""Entrée CLI du DigestBuilder — invoquée par cron / Task Scheduler.

Usage::

    uv run python scripts/run_digest.py

Sortie : 0 si success, 1 si failed/killed_by_breaker. Tous les détails
(KPIs, erreurs) sont loggés via loguru et persistés dans ``agent_runs``.

Cf. D-017 : ce script tourne sur l'ordi du fondateur via Task Scheduler
Windows ou cron WSL2, pas sur le serveur SecHunter.
"""

from __future__ import annotations

import asyncio
import sys

from loguru import logger

from argos_ops.agents.base import run_agent
from argos_ops.agents.digest_builder import DigestBuilder
from argos_ops.crm.db import dispose_engine


async def amain() -> int:
    try:
        result = await run_agent(DigestBuilder())
    finally:
        await dispose_engine()

    if result.status == "success":
        logger.success(f"DigestBuilder OK — {result.output_summary}")
        return 0
    logger.error(f"DigestBuilder {result.status} — {result.error}")
    return 1


def main() -> int:
    # psycopg async exige SelectorEventLoop sur Windows.
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    return asyncio.run(amain())


if __name__ == "__main__":
    sys.exit(main())
