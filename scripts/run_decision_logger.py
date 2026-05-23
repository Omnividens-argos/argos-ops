"""Entrée CLI du DecisionLogger — health-check passif.

L'append interactif passe par :func:`append_decision` invoqué depuis
le slash command ``/log-decision``. Ce script vérifie juste la
lisibilité du journal canonique ``docs/DECISIONS.md``.

Usage::

    uv run python scripts/run_decision_logger.py
"""

from __future__ import annotations

import asyncio
import sys

from loguru import logger

from argos_ops.agents.base import run_agent
from argos_ops.agents.decision_logger import DEFAULT_DECISIONS_PATH, DecisionLogger
from argos_ops.crm.db import dispose_engine


async def amain() -> int:
    try:
        result = await run_agent(DecisionLogger(output_path=DEFAULT_DECISIONS_PATH))
    finally:
        await dispose_engine()

    if result.status == "success":
        logger.success(f"DecisionLogger OK — {result.output_summary}")
        return 0
    logger.error(f"DecisionLogger {result.status} — {result.error}")
    return 1


def main() -> int:
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    return asyncio.run(amain())


if __name__ == "__main__":
    sys.exit(main())
