"""Diagnostic CLI Argos Ops (P19) — vérifie la santé du système.

Usage :
    uv run python scripts/health_check.py
    uv run python scripts/health_check.py --json
    uv run python scripts/health_check.py --no-notify

Lance la batterie de checks de ``argos_ops.health`` puis affiche un
rapport humain (ou JSON pour parsing). Si le statut global n'est pas
``green`` ET ``DISCORD_WEBHOOK_OPS_LOGS`` est configuré, pousse une
notif Discord (sauf si ``--no-notify``).

Exit code :
- 0 si overall green
- 1 si overall yellow
- 2 si overall red

À mettre en cron quotidien (Task Scheduler Windows) — proposé : 5h45,
juste avant le digest 8h, pour catch les regressions overnight.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime

from loguru import logger

from argos_ops.config import get_settings
from argos_ops.crm.db import dispose_engine, session_scope
from argos_ops.health import (
    HealthCheck,
    HealthStatus,
    aggregate_health,
    run_all_checks,
)
from argos_ops.notifications.discord import (
    GREEN,
    RED,
    YELLOW,
    Embed,
    EmbedField,
    send_embed,
)

_STATUS_ICON: dict[HealthStatus, str] = {"green": "[OK]", "yellow": "[WARN]", "red": "[FAIL]"}
_STATUS_COLOR: dict[HealthStatus, int] = {"green": GREEN, "yellow": YELLOW, "red": RED}
_EXIT_CODES: dict[HealthStatus, int] = {"green": 0, "yellow": 1, "red": 2}


def _format_human(overall: HealthCheck, checks: list[HealthCheck]) -> str:
    lines = [
        "=" * 60,
        f"Argos Ops — health check {datetime.now().isoformat(timespec='seconds')}",
        "=" * 60,
        f"Overall : {_STATUS_ICON[overall.status]} {overall.status.upper()} — {overall.detail}",
        "-" * 60,
    ]
    for check in checks:
        lines.append(f"{_STATUS_ICON[check.status]:7} {check.name:25} {check.detail}")
    lines.append("=" * 60)
    return "\n".join(lines)


def _build_embed(overall: HealthCheck, checks: list[HealthCheck]) -> Embed:
    fields = [
        EmbedField(
            name=f"{_STATUS_ICON[c.status]} {c.name}",
            value=c.detail[:1020] if len(c.detail) > 1020 else c.detail,
            inline=False,
        )
        for c in checks
    ]
    return Embed(
        title=f"Argos Ops health — {overall.status.upper()}",
        description=overall.detail,
        color=_STATUS_COLOR[overall.status],
        fields=fields,
        timestamp=datetime.now().isoformat(),
    )


async def _amain(*, output_json: bool, notify: bool) -> int:
    settings = get_settings()
    async with session_scope() as session:
        checks = await run_all_checks(session)
    overall = aggregate_health(checks)

    if output_json:
        payload = {
            "overall": {
                "status": overall.status,
                "detail": overall.detail,
                "metric": overall.metric,
            },
            "checks": [
                {
                    "name": c.name,
                    "status": c.status,
                    "detail": c.detail,
                    "metric": c.metric,
                }
                for c in checks
            ],
        }
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print(_format_human(overall, checks))

    if notify and overall.status != "green" and settings.discord_webhook_ops_logs is not None:
        try:
            await send_embed(settings.discord_webhook_ops_logs, _build_embed(overall, checks))
            logger.info(f"Notif Discord envoyée (status={overall.status})")
        except Exception as exc:  # le check passe quand même, on log juste
            logger.error(f"Discord notif failed : {type(exc).__name__}: {exc}")
    elif notify and overall.status != "green":
        logger.warning(
            f"DISCORD_WEBHOOK_OPS_LOGS non configuré — notif skip (overall={overall.status})"
        )

    return _EXIT_CODES[overall.status]


def main() -> int:
    parser = argparse.ArgumentParser(description="Argos Ops health check (P19)")
    parser.add_argument(
        "--json",
        action="store_true",
        help="Sortie en JSON (utile pour piping / dashboard)",
    )
    parser.add_argument(
        "--no-notify",
        action="store_true",
        help="Ne pas pousser de notif Discord même si overall != green",
    )
    args = parser.parse_args()

    # psycopg async sur Windows
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    try:
        return asyncio.run(_amain(output_json=args.json, notify=not args.no_notify))
    finally:
        asyncio.run(dispose_engine())


if __name__ == "__main__":
    sys.exit(main())
