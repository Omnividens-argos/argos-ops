"""Entrée CLI du ADRWriter (P22.F Sprint 13).

Usage::

    cat draft.json | uv run python scripts/run_adr_writer.py [slug]

Lit un JSON sur stdin avec les champs ``title`` / ``context`` /
``decision`` / ``consequences`` (et optionnellement ``status``). Le
``slug`` peut être passé en argument CLI ou dérivé du title.
"""

from __future__ import annotations

import asyncio
import json
import sys

from loguru import logger

from argos_ops.agents.adr_writer import ADRWriter, build_draft
from argos_ops.agents.base import run_agent
from argos_ops.crm.db import dispose_engine


async def amain(slug: str | None) -> int:
    if sys.stdin.isatty():
        logger.error(
            "Aucun JSON sur stdin — pipe un fichier draft "
            "(ex: cat draft.json | run_adr_writer.py mon-slug)"
        )
        return 2
    try:
        payload = json.loads(sys.stdin.read())
    except json.JSONDecodeError as exc:
        logger.error(f"JSON invalide : {exc}")
        return 2

    try:
        draft = build_draft(
            title=payload["title"],
            context=payload["context"],
            decision=payload["decision"],
            consequences=payload["consequences"],
            status=payload.get("status", "proposed"),
            slug=slug or payload.get("slug"),
        )
    except KeyError as exc:
        logger.error(f"Champ obligatoire manquant : {exc}")
        return 2
    except ValueError as exc:
        logger.error(str(exc))
        return 2

    try:
        result = await run_agent(ADRWriter(draft))
    finally:
        await dispose_engine()

    if result.status == "success":
        logger.success(f"ADRWriter OK — {result.output_summary}")
        return 0
    logger.error(f"ADRWriter {result.status} — {result.error}")
    return 1


def main() -> int:
    slug = sys.argv[1] if len(sys.argv) >= 2 else None
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    return asyncio.run(amain(slug))


if __name__ == "__main__":
    sys.exit(main())
