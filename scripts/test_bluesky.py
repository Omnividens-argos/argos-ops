"""Test live d'un post Bluesky via BlueskyClient (le client de prod).

Usage :
    uv run python scripts/test_bluesky.py
    uv run python scripts/test_bluesky.py --message "texte custom"
    uv run python scripts/test_bluesky.py --dry-run   # shadow, ne poste pas

Si BLUESKY_HANDLE ou BLUESKY_APP_PASSWORD manque dans .env.local, le client
retombe automatiquement en shadow mode — utile pour valider le branchement
sans rien publier. Setup : bsky.app -> Settings -> App Passwords.

Sortie : URL du post publié si succès, code retour non-zéro sinon.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys

from dotenv import load_dotenv
from pydantic import SecretStr

from argos_ops.social.bluesky import MAX_GRAPHEMES, BlueskyClient

DEFAULT_MESSAGE = (
    "Test de connexion API Argos Ops — ignorez ce post. "
    "On scanne, vous corrigez. https://omnividens.fr #infosec"
)


async def run(message: str, dry_run: bool) -> int:
    load_dotenv(".env.local")
    handle = os.environ.get("BLUESKY_HANDLE", "").strip()
    app_password = os.environ.get("BLUESKY_APP_PASSWORD", "").strip()
    pds_url = os.environ.get("BLUESKY_PDS_URL", "https://bsky.social").strip()

    client = BlueskyClient(
        handle=handle or None,
        app_password=SecretStr(app_password) if app_password else None,
        pds_url=pds_url or "https://bsky.social",
    )
    mode = "LIVE" if client.is_live and not dry_run else "SHADOW"
    print(f"[+] Handle   : {handle or '(absent)'}")
    print(f"[+] PDS      : {pds_url}")
    print(f"[+] Mode     : {mode}")
    print(f"[+] Message  : {message}")
    print(f"[+] Longueur : {len(message)} chars (max {MAX_GRAPHEMES} graphemes)")

    if len(message) > MAX_GRAPHEMES:
        print(f"FAIL — message > {MAX_GRAPHEMES} graphemes")
        return 2

    if mode == "SHADOW" and not dry_run:
        print(
            "[i] Credentials Bluesky absents — rien posté. "
            "Remplir BLUESKY_HANDLE + BLUESKY_APP_PASSWORD dans .env.local "
            "(bsky.app -> Settings -> App Passwords) pour un test live."
        )

    result = await client.post(message, dry_run=dry_run)
    status = result.get("status")
    url = result.get("url")
    error = result.get("error")

    if status == "published":
        print(f"[OK] Publié — URL : {url}")
        return 0
    if status == "shadow":
        print("[OK] Shadow mode — rien posté (credentials absents ou --dry-run).")
        return 0
    print(f"FAIL — status={status} error={error}")
    return 3


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--message", default=DEFAULT_MESSAGE, help="texte du post")
    parser.add_argument("--dry-run", action="store_true", help="force shadow mode")
    args = parser.parse_args()
    return asyncio.run(run(args.message, args.dry_run))


if __name__ == "__main__":
    sys.exit(main())
