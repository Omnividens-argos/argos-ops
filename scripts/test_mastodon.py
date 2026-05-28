"""Test live d'un toot Mastodon via MastodonClient (le client de prod).

Usage :
    uv run python scripts/test_mastodon.py
    uv run python scripts/test_mastodon.py --message "texte custom"
    uv run python scripts/test_mastodon.py --dry-run   # shadow, ne poste pas

Si MASTODON_ACCESS_TOKEN est absent de .env.local, le client retombe
automatiquement en shadow mode (D-025) — utile pour tester le branchement
sans risquer de publier.

Sortie : URL du toot publié si succès, code retour non-zéro sinon.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys

from dotenv import load_dotenv
from pydantic import SecretStr

from argos_ops.social.mastodon import MastodonClient

DEFAULT_MESSAGE = (
    "Test de connexion API Argos Ops — ignorez ce toot. "
    "https://omnividens.fr"
)


async def run(message: str, dry_run: bool) -> int:
    load_dotenv(".env.local")
    instance_url = os.environ.get("MASTODON_INSTANCE_URL", "").strip()
    token = os.environ.get("MASTODON_ACCESS_TOKEN", "").strip()

    if not instance_url:
        print("FAIL — MASTODON_INSTANCE_URL manquant dans .env.local")
        return 1

    client = MastodonClient(
        instance_url=instance_url,
        access_token=SecretStr(token) if token else None,
    )
    mode = "LIVE" if client.is_live and not dry_run else "SHADOW"
    print(f"[+] Instance : {instance_url}")
    print(f"[+] Mode     : {mode}")
    print(f"[+] Message  : {message}")
    print(f"[+] Longueur : {len(message)} chars (max 500 sur Mastodon)")

    if len(message) > 500:
        print("FAIL — message > 500 chars")
        return 2

    result = await client.post(message, dry_run=dry_run)
    status = result.get("status")
    url = result.get("url")
    error = result.get("error")

    if status == "published":
        print(f"[OK] Publié — URL : {url}")
        return 0
    if status == "shadow":
        print("[OK] Shadow mode — rien posté (token absent ou --dry-run).")
        return 0
    print(f"FAIL — status={status} error={error}")
    return 3


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--message", default=DEFAULT_MESSAGE, help="texte du toot")
    parser.add_argument("--dry-run", action="store_true", help="force shadow mode")
    args = parser.parse_args()
    return asyncio.run(run(args.message, args.dry_run))


if __name__ == "__main__":
    sys.exit(main())
