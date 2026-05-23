"""Entrée CLI du RGPDAuditor — invoqué par cron / Task Scheduler.

Usage::

    uv run python scripts/run_rgpd_auditor.py

Cf. :mod:`argos_ops.agents.rgpd_auditor`. Politique : silence si tous
les findings PII sont couverts par ``data/compliance/rgpd_registry.yaml``.
"""

from __future__ import annotations

import asyncio
import sys

from loguru import logger

from argos_ops.agents.base import run_agent
from argos_ops.agents.rgpd_auditor import RGPDAuditor
from argos_ops.crm.db import dispose_engine


async def amain() -> int:
    try:
        result = await run_agent(RGPDAuditor())
    finally:
        await dispose_engine()

    if result.status == "success":
        logger.success(f"RGPDAuditor OK — {result.output_summary}")
        return 0
    logger.error(f"RGPDAuditor {result.status} — {result.error}")
    return 1


def main() -> int:
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    return asyncio.run(amain())


if __name__ == "__main__":
    sys.exit(main())
