"""Entrée CLI du ExpenseAuditor (P22.F Sprint 10)."""

from __future__ import annotations

import asyncio
import sys

from loguru import logger

from argos_ops.agents.base import run_agent
from argos_ops.agents.expense_auditor import ExpenseAuditor
from argos_ops.crm.db import dispose_engine


async def amain() -> int:
    try:
        result = await run_agent(ExpenseAuditor())
    finally:
        await dispose_engine()
    if result.status == "success":
        logger.success(f"ExpenseAuditor OK — {result.output_summary}")
        return 0
    logger.error(f"ExpenseAuditor {result.status} — {result.error}")
    return 1


def main() -> int:
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    return asyncio.run(amain())


if __name__ == "__main__":
    sys.exit(main())
