"""Test live d'un post X (ex-Twitter) via TwitterClient (le client de prod).

Usage :
    uv run python scripts/test_twitter.py
    uv run python scripts/test_twitter.py --message "texte custom"
    uv run python scripts/test_twitter.py --dry-run   # shadow, ne poste pas

Si X_ACCESS_TOKEN est absent de .env.local, le client retombe en shadow mode
— utile pour valider le branchement sans rien publier. Le canal X est
draft-only / activation reportée : ne lancer le mode live qu'une fois le tier
API X arbitré (Free vs Basic) et le token user-context OAuth 2.0 obtenu.

Sortie : URL du tweet publié si succès, code retour non-zéro sinon.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys

from dotenv import load_dotenv
from pydantic import SecretStr

from argos_ops.social.twitter import MAX_CHARS, TwitterClient

DEFAULT_MESSAGE = (
    "Test de connexion API Argos Ops — ignorez ce post. "
    "On scanne, vous corrigez. https://omnividens.fr"
)


async def run(message: str, dry_run: bool) -> int:
    load_dotenv(".env.local")
    token = os.environ.get("X_ACCESS_TOKEN", "").strip()
    api_base = os.environ.get("X_API_BASE", "https://api.twitter.com").strip()

    client = TwitterClient(
        access_token=SecretStr(token) if token else None,
        api_base=api_base or "https://api.twitter.com",
    )
    mode = "LIVE" if client.is_live and not dry_run else "SHADOW"
    print(f"[+] Mode     : {mode}")
    print(f"[+] Message  : {message}")
    print(f"[+] Longueur : {len(message)} chars (max {MAX_CHARS})")

    if len(message) > MAX_CHARS:
        print(f"FAIL — message > {MAX_CHARS} chars")
        return 2

    if mode == "SHADOW" and not dry_run:
        print(
            "[i] X_ACCESS_TOKEN absent — rien posté. Remplir le token "
            "user-context OAuth 2.0 (scope tweet.write) dans .env.local pour "
            "un test live (canal draft-only, activation reportée)."
        )

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
    parser.add_argument("--message", default=DEFAULT_MESSAGE, help="texte du tweet")
    parser.add_argument("--dry-run", action="store_true", help="force shadow mode")
    args = parser.parse_args()
    return asyncio.run(run(args.message, args.dry_run))


if __name__ == "__main__":
    sys.exit(main())
