"""Démo runnable du pôle **Marketing** (archi v2, S2) : scripts → mémoire → agent.

Usage :
    uv run python scripts/poles_marketing_demo.py

Lance les 3 scripts déterministes du pôle (ContentBot publie les drafts validés
échus, SocialAnalytics agrège l'engagement, MediaListBuilder audite la DB
médias — chacun écrit sa mémoire), puis le :class:`MarketingAgent` qui relit
**sa mémoire propre + la mémoire de la Veille en cross-pôle** et la synthétise en
**recommandations de contenu routées par canal**.

Idempotent : relancer ne duplique aucun fait (identité = hash du corps). Si
aucune source n'est configurée, l'agent lira au moins les faits d'exemple
commités (mémoire Marketing + Veille).

Exit code : 0 si l'agent a pu agir (status ``success``), 1 sinon.
"""

from __future__ import annotations

import asyncio
import sys

from loguru import logger

from argos_ops.poles.base import run_script
from argos_ops.poles.marketing.agent import MarketingAgent
from argos_ops.poles.marketing.scripts import MARKETING_SCRIPTS


async def _amain() -> int:
    logger.info("=== Demo Marketing (archi v2) -- scripts -> memoire -> agent ===")

    logger.info(f"[1/2] {len(MARKETING_SCRIPTS)} SCRIPTS deterministes")
    for script_cls in MARKETING_SCRIPTS:
        result = await run_script(script_cls())
        logger.info(
            f"      -> {script_cls.__name__}: {result.status} "
            f"({len(result.written)} fait[s]) -- {result.summary or ''}"
        )

    logger.info("[2/2] AGENT MarketingAgent.run() (lit sa memoire + la Veille en cross-pole)")
    agent_result = await MarketingAgent().run()
    logger.info(f"      -> {agent_result.status} -- {agent_result.summary}")
    for action in agent_result.actions:
        logger.info(f"      -> reco : {action}")

    if agent_result.status == "success":
        logger.success("Flux Marketing demontre : les scripts ont ecrit, l'agent a recommande.")
        return 0
    logger.warning("Aucune memoire editorialisable -- l'agent n'a rien a recommander.")
    return 1


def main() -> int:
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    return asyncio.run(_amain())


if __name__ == "__main__":
    sys.exit(main())
