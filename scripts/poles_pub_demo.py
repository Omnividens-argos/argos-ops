"""Démo runnable du pôle **Pub** (archi v2, S3) : scripts → mémoire → agent.

Usage :
    uv run python scripts/poles_pub_demo.py

Lance les 2 scripts déterministes du pôle (AdsOptimizer lit les CSV de campagnes,
chiffre les recos et arme la jauge/breaker ; AdBot pousse en shadow — chacun écrit
sa mémoire), puis le :class:`PubAgent` qui relit **sa mémoire propre + Veille +
Marketing + Finance en cross-pôle** et la synthétise en **plan d'actions** borné
par le breaker ``ad_spend_runaway``.

Idempotent : relancer ne duplique aucun fait (identité = hash du corps). Si aucune
campagne / créa n'est configurée, l'agent lira au moins les faits d'exemple
commités.

Exit code : 0 si l'agent a pu agir (status ``success``), 1 sinon.
"""

from __future__ import annotations

import asyncio
import sys

from loguru import logger

from argos_ops.poles.base import run_script
from argos_ops.poles.pub import budget
from argos_ops.poles.pub.agent import PubAgent
from argos_ops.poles.pub.scripts import PUB_SCRIPTS


async def _amain() -> int:
    logger.info("=== Demo Pub (archi v2) -- scripts -> memoire -> agent ===")

    logger.info(f"[1/2] {len(PUB_SCRIPTS)} SCRIPTS deterministes")
    for script_cls in PUB_SCRIPTS:
        result = await run_script(script_cls())
        logger.info(
            f"      -> {script_cls.__name__}: {result.status} "
            f"({len(result.written)} fait[s]) -- {result.summary or ''}"
        )

    state = budget.load_budget()
    logger.info(
        f"      -> jauge budget : {state.spent_per_day_eur:.0f} EUR/j "
        f"/ {state.daily_budget_eur:.0f} EUR/j -- breaker {'ARME' if state.breaker_tripped else 'OK'}"
    )

    logger.info("[2/2] AGENT PubAgent.run() (lit sa memoire + Veille/Marketing/Finance en cross-pole)")
    agent_result = await PubAgent().run()
    logger.info(f"      -> {agent_result.status} -- {agent_result.summary}")
    for action in agent_result.actions:
        logger.info(f"      -> plan : {action}")

    if agent_result.status == "success":
        logger.success("Flux Pub demontre : les scripts ont chiffre, l'agent a planifie.")
        return 0
    logger.warning("Aucune memoire actionnable -- l'agent n'a rien a planifier.")
    return 1


def main() -> int:
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    return asyncio.run(_amain())


if __name__ == "__main__":
    sys.exit(main())
