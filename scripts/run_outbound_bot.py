"""Entrée CLI OutboundBot — scaffold séquences cold email (P13.A shadow).

Usage::

    uv run python scripts/run_outbound_bot.py

OutboundBot lit ``data/outbound/inbox/leads.csv`` et scaffold les
séquences manquantes dans ``data/outbound/sequences/<slug>/``. Aucun
envoi en P13.A — c'est OutboundSender (P13.B) qui s'occupe du SMTP
quand ``OUTBOUND_LIVE_MODE=true``.
"""

from __future__ import annotations

import asyncio
import sys

from loguru import logger

from argos_ops.agents.base import run_agent
from argos_ops.agents.outbound_bot import OutboundBot
from argos_ops.crm.db import dispose_engine


async def amain() -> int:
    try:
        result = await run_agent(OutboundBot())
    finally:
        await dispose_engine()
    if result.status == "success":
        logger.success(f"OutboundBot OK — {result.output_summary}")
        return 0
    logger.error(f"OutboundBot {result.status} — {result.error}")
    return 1


def main() -> int:
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    return asyncio.run(amain())


if __name__ == "__main__":
    sys.exit(main())
