"""Entrée CLI du IncidentLogger — health-check passif.

Le scaffold interactif passe par :func:`scaffold_incident` invoqué
depuis le slash command ``/log-incident``. Ce script vérifie juste
l'accessibilité du dossier ``data/compliance/incidents/``.

Usage::

    uv run python scripts/run_incident_logger.py
"""

from __future__ import annotations

import asyncio
import sys

from loguru import logger

from argos_ops.agents.base import run_agent
from argos_ops.agents.incident_logger import IncidentLogger
from argos_ops.crm.db import dispose_engine


async def amain() -> int:
    try:
        result = await run_agent(IncidentLogger())
    finally:
        await dispose_engine()

    if result.status == "success":
        logger.success(f"IncidentLogger OK — {result.output_summary}")
        return 0
    logger.error(f"IncidentLogger {result.status} — {result.error}")
    return 1


def main() -> int:
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    return asyncio.run(amain())


if __name__ == "__main__":
    sys.exit(main())
