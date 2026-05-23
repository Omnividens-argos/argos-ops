"""Entrée CLI du DependencyAuditor — invoquée par cron / Task Scheduler.

Usage::

    uv run python scripts/run_dependency_auditor.py

Cf. :mod:`argos_ops.agents.dependency_auditor`. Politique : silence si
aucune vuln MEDIUM+, embed jaune si MEDIUM, rouge si HIGH/CRITICAL.

Réseau requis : appelle l'API publique OSV.dev (https://api.osv.dev).
"""

from __future__ import annotations

import asyncio
import sys

from loguru import logger

from argos_ops.agents.base import run_agent
from argos_ops.agents.dependency_auditor import DependencyAuditor
from argos_ops.crm.db import dispose_engine


async def amain() -> int:
    try:
        result = await run_agent(DependencyAuditor())
    finally:
        await dispose_engine()

    if result.status == "success":
        logger.success(f"DependencyAuditor OK — {result.output_summary}")
        return 0
    logger.error(f"DependencyAuditor {result.status} — {result.error}")
    return 1


def main() -> int:
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    return asyncio.run(amain())


if __name__ == "__main__":
    sys.exit(main())
