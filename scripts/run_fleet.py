"""Entrée CLI de l'orchestrateur de **flotte** (archi v2, S9).

Chef des 8 pôles : décide quels scripts (tous pôles confondus) doivent tourner
*maintenant* à partir de la cadence cron déclarée dans chaque ``pole.yaml`` + du
kill-switch + des breakers + des limites quotidiennes, puis — en mode live —
lance les scripts dûs et **réveille l'agent** de chaque pôle dont des scripts ont
rafraîchi la mémoire (cycle ``script → mémoire → agent → action``).

Usage::

    uv run python scripts/run_fleet.py                 # dry-run (défaut) : logue le plan
    uv run python scripts/run_fleet.py --live          # exécute réellement
    uv run python scripts/run_fleet.py --no-agents     # scripts seuls, pas de réveil d'agent
    uv run python scripts/run_fleet.py --max-concurrent 3

Mode **dry-run par défaut** — refuse de lancer quoi que ce soit tant que
``--live`` n'est pas passé explicitement (garde-fou contre un cron malencontreux,
d'autant que certains scripts ont des effets de bord hors ``poles_root`` en live :
diagram_generator/adr_writer écrivent dans ``docs/``, les watchers Veille touchent
le réseau). Sortie : 0 si tout OK, 1 si au moins un script/agent a échoué.

Cet orchestrateur v2 (file-based, local-first D-017) est **distinct** de l'ancien
``scripts/run_orchestrator.py`` (DB-based, legacy ``argos_ops.agents``).
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from loguru import logger

from argos_ops.poles.fleet import (
    DEFAULT_MAX_CONCURRENT,
    plan_fleet,
    run_fleet_cycle,
)


async def amain(*, live: bool, trigger_agents: bool, max_concurrent: int | None) -> int:
    plan = await plan_fleet(
        dry_run=not live,
        trigger_agents=trigger_agents,
        max_concurrent=max_concurrent,
    )
    logger.info(f"fleet — {plan.summary()}")
    for decision in plan.decisions:
        line = (
            f"[{decision.verdict}] {decision.pole}/{decision.script} — "
            f"runs_today={decision.runs_today} reason={decision.reason}"
        )
        logger.info(line) if decision.verdict == "launch" else logger.debug(line)

    if not live:
        logger.success(f"fleet dry-run — {plan.summary()} (aucun lancement)")
        return 0

    result = await run_fleet_cycle(plan)
    failed = sum(1 for o in result.script_outcomes if o.status == "failed")
    failed += sum(1 for o in result.agent_outcomes if o.status == "failed")
    logger.success(f"fleet live — {result.summary()}")
    return 1 if failed else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Orchestrateur de flotte Argos Ops (archi v2)")
    parser.add_argument(
        "--live",
        action="store_true",
        help="Mode live : lance réellement les scripts dûs + réveille les agents (défaut = dry-run)",
    )
    parser.add_argument(
        "--no-agents",
        action="store_true",
        help="Ne pas réveiller les agents après les scripts (scripts seuls)",
    )
    parser.add_argument(
        "--max-concurrent",
        type=int,
        default=None,
        help=(
            "Nombre max de scripts lancés en parallèle. Si omis, on prend "
            f"data/poles/fleet.yaml (sinon {DEFAULT_MAX_CONCURRENT})."
        ),
    )
    args = parser.parse_args()

    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    return asyncio.run(
        amain(
            live=args.live,
            trigger_agents=not args.no_agents,
            max_concurrent=args.max_concurrent,
        )
    )


if __name__ == "__main__":
    sys.exit(main())
