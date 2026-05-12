"""CLI helper pour reset un breaker (P15).

Usage :
    uv run python scripts/reset_breaker.py <name>
    uv run python scripts/reset_breaker.py --list           # affiche les breakers tripped

Invoqué par le slash command ``/reset-breaker`` ou en direct depuis le
terminal. Pas de daemon, exécution one-shot.
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from loguru import logger

from argos_ops.breakers import list_tripped, reset, status


async def _list_tripped() -> int:
    items = await list_tripped()
    if not items:
        logger.info("Aucun breaker tripped actuellement.")
        return 0
    logger.info(f"{len(items)} breaker(s) tripped :")
    for b in items:
        reset_after_str = f" (reset auto: {b.reset_after.isoformat()})" if b.reset_after else ""
        logger.info(f"  • {b.name} — {b.reason}{reset_after_str}")
    return 0


async def _reset_one(name: str) -> int:
    current = await status(name)
    if current is None or not current.tripped:
        logger.info(f"Breaker '{name}' n'est pas tripped — rien à faire.")
        return 0
    await reset(name)
    logger.success(f"Breaker '{name}' reseté.")
    return 0


def _main() -> int:
    if sys.platform == "win32":  # psycopg async exige le SelectorEventLoop sur Windows
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    parser = argparse.ArgumentParser(description="Reset un circuit breaker Argos Ops (P15).")
    parser.add_argument("name", nargs="?", help="Nom du breaker à reset")
    parser.add_argument(
        "--list", action="store_true", help="Liste les breakers actuellement tripped"
    )
    args = parser.parse_args()

    if args.list or args.name is None:
        return asyncio.run(_list_tripped())
    return asyncio.run(_reset_one(args.name))


if __name__ == "__main__":
    sys.exit(_main())
