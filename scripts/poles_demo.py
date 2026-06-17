"""Démo runnable du flux archi v2 : script → mémoire → agent (pôle ``_example``).

Usage :
    uv run python scripts/poles_demo.py

Lance :class:`HeartbeatScript` (écrit un fait dans
``data/poles/_example/scripts/heartbeat/memory/``) puis :class:`ExampleAgent`
(relit ce fait et agit dessus). Idempotent : relancer ne duplique rien
(identité du fait = hash du corps).

Exit code :
- 0 si l'agent a bien lu et agi (status ``success``)
- 1 sinon
"""

from __future__ import annotations

import asyncio
import sys

from loguru import logger

from argos_ops.poles.base import run_script
from argos_ops.poles.example import ExampleAgent, HeartbeatScript


async def _amain() -> int:
    logger.info("=== Demo archi v2 -- flux script -> memoire -> agent (_example) ===")

    logger.info("[1/2] SCRIPT deterministe : HeartbeatScript.run()")
    script_result = await run_script(HeartbeatScript())
    logger.info(f"      -> {script_result.status} -- {script_result.summary}")
    for rec in script_result.written:
        logger.info(f"      -> memoire ecrite : {rec.pole}/{rec.script}/{rec.id} -- {rec.body!r}")

    logger.info("[2/2] AGENT cerveau : ExampleAgent.run() (charge la memoire puis agit)")
    agent_result = await ExampleAgent().run()
    logger.info(f"      -> {agent_result.status} -- {agent_result.summary}")

    if agent_result.status == "success":
        logger.success("Flux démontré : le script a écrit, l'agent a lu et agi.")
        return 0
    logger.error("Flux KO : l'agent n'a pas pu agir.")
    return 1


def main() -> int:
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    return asyncio.run(_amain())


if __name__ == "__main__":
    sys.exit(main())
