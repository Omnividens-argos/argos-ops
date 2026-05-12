"""Lance le backend FastAPI de l'Admin Control Panel (P16.A) en local.

Usage :
    uv run python scripts/run_ops_dashboard.py

Sert l'API sur ``http://127.0.0.1:9000`` (cohérent avec le port prévu dans
le Caddyfile prod, cf. ``ARGOS_OPS_PLAN.md`` § 16.3). Le frontend Vite
appellera ces endpoints depuis ``http://localhost:5173``.

En prod (P16.B), un service systemd remplacera ce script.
"""

from __future__ import annotations

import sys

import uvicorn


def main() -> int:
    if sys.platform == "win32":
        # psycopg async exige SelectorEventLoop sur Windows
        import asyncio

        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    uvicorn.run(
        "argos_ops.ops_dashboard.app:app",
        host="127.0.0.1",
        port=9000,
        reload=True,
        log_level="info",
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
