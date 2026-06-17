"""Démo runnable du pôle **Veille** (archi v2, S1) : scripts → mémoire → agent.

Usage :
    uv run python scripts/poles_veille_demo.py

Lance les 9 scripts déterministes du pôle (chacun écrit sa mémoire si ses
sources sont présentes — sinon il no-op proprement, local-first D-017), puis le
:class:`VeilleAgent` qui relit toute la mémoire du pôle et la **synthétise en
insights routés** vers Marketing / Pub / Vente.

Idempotent : relancer ne duplique aucun fait (identité = hash du corps). Si
aucune source n'est configurée, l'agent lira au moins les faits d'exemple
commités sous ``data/poles/veille/scripts/*/memory/``.

Exit code : 0 si l'agent a pu agir (status ``success``), 1 sinon (mémoire vide).
"""

from __future__ import annotations

import asyncio
import sys

from loguru import logger

from argos_ops.poles.base import run_script
from argos_ops.poles.veille.agent import VeilleAgent
from argos_ops.poles.veille.scripts import VEILLE_SCRIPTS


async def _amain() -> int:
    logger.info("=== Demo Veille (archi v2) -- scripts -> memoire -> agent ===")

    logger.info(f"[1/2] {len(VEILLE_SCRIPTS)} SCRIPTS deterministes")
    for script_cls in VEILLE_SCRIPTS:
        result = await run_script(script_cls())
        logger.info(
            f"      -> {script_cls.__name__}: {result.status} "
            f"({len(result.written)} fait[s]) -- {result.summary or ''}"
        )

    logger.info("[2/2] AGENT VeilleAgent.run() (lit la memoire du pole et synthetise)")
    agent_result = await VeilleAgent().run()
    logger.info(f"      -> {agent_result.status} -- {agent_result.summary}")
    for action in agent_result.actions:
        logger.info(f"      -> insight : {action}")

    if agent_result.status == "success":
        logger.success("Flux Veille demontre : les scripts ont ecrit, l'agent a synthetise.")
        return 0
    logger.warning("Aucun signal en memoire -- l'agent n'a rien a synthetiser.")
    return 1


def main() -> int:
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    return asyncio.run(_amain())


if __name__ == "__main__":
    sys.exit(main())
