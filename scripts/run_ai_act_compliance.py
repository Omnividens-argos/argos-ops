"""Entrée CLI du AIActComplianceBot.

Usage::

    uv run python scripts/run_ai_act_compliance.py

Cf. :mod:`argos_ops.agents.ai_act_compliance`. Politique : silence si
tous les agents ont un ``ai_act_risk_class`` valide.
"""

from __future__ import annotations

import asyncio
import sys

from loguru import logger

from argos_ops.agents.ai_act_compliance import AIActComplianceBot
from argos_ops.agents.base import run_agent
from argos_ops.crm.db import dispose_engine


async def amain() -> int:
    try:
        result = await run_agent(AIActComplianceBot())
    finally:
        await dispose_engine()

    if result.status == "success":
        logger.success(f"AIActComplianceBot OK — {result.output_summary}")
        return 0
    logger.error(f"AIActComplianceBot {result.status} — {result.error}")
    return 1


def main() -> int:
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    return asyncio.run(amain())


if __name__ == "__main__":
    sys.exit(main())
