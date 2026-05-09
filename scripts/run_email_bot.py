"""Entrée CLI de l'EmailBot — invoquée par cron / Task Scheduler.

Usage::

    uv run python scripts/run_email_bot.py

Sortie : 0 si success, 1 si failed/killed_by_breaker. Tous les détails
(stats d'ingestion, erreurs IMAP) sont loggés via loguru et persistés dans
``agent_runs``.

Cf. D-017 : tourne sur l'ordi du fondateur via Task Scheduler Windows
(cadence ``*/15 * * * *`` Paris). D-018 : OVH Zimbra IMAP/SMTP.
"""

from __future__ import annotations

import asyncio
import sys

from loguru import logger

from argos_ops.agents.base import run_agent
from argos_ops.agents.email_bot import EmailBot
from argos_ops.crm.db import dispose_engine


async def amain() -> int:
    try:
        result = await run_agent(EmailBot())
    finally:
        await dispose_engine()

    if result.status == "success":
        logger.success(f"EmailBot OK — {result.output_summary}")
        return 0
    logger.error(f"EmailBot {result.status} — {result.error}")
    return 1


def main() -> int:
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    return asyncio.run(amain())


if __name__ == "__main__":
    sys.exit(main())
