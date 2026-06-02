"""Test live d'un post Truth Social via TruthSocialClient (le client de prod).

Usage :
    uv run python scripts/test_truth_social.py
    uv run python scripts/test_truth_social.py --message "texte custom"
    uv run python scripts/test_truth_social.py --dry-run   # shadow, ne poste pas

Si TRUTH_SOCIAL_ACCESS_TOKEN est absent de .env.local, le client retombe en
shadow mode — utile pour valider le branchement sans rien publier. L'accès
API Truth Social n'étant pas ouvert librement, ce mode live n'est testable
qu'une fois l'accès accordé au fondateur. Canal expérimental, draft-only.

Sortie : URL du post publié si succès, code retour non-zéro sinon.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys

from dotenv import load_dotenv
from pydantic import SecretStr

from argos_ops.social.truth_social import MAX_CHARS, TruthSocialClient

DEFAULT_MESSAGE = (
    "Connection test from Argos Ops — please ignore. "
    "Knowing whether your website is protected should be simple. https://omnividens.fr"
)


async def run(message: str, dry_run: bool) -> int:
    load_dotenv(".env.local")
    instance_url = os.environ.get("TRUTH_SOCIAL_INSTANCE_URL", "https://truthsocial.com").strip()
    token = os.environ.get("TRUTH_SOCIAL_ACCESS_TOKEN", "").strip()

    client = TruthSocialClient(
        instance_url=instance_url or "https://truthsocial.com",
        access_token=SecretStr(token) if token else None,
    )
    mode = "LIVE" if client.is_live and not dry_run else "SHADOW"
    print(f"[+] Instance : {instance_url}")
    print(f"[+] Mode     : {mode}")
    print(f"[+] Message  : {message}")
    print(f"[+] Longueur : {len(message)} chars (max {MAX_CHARS})")

    if len(message) > MAX_CHARS:
        print(f"FAIL — message > {MAX_CHARS} chars")
        return 2

    if mode == "SHADOW" and not dry_run:
        print(
            "[i] TRUTH_SOCIAL_ACCESS_TOKEN absent — rien posté. L'accès API "
            "est à demander par le fondateur avant tout test live (canal "
            "draft-only / expérimental)."
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
    parser.add_argument("--message", default=DEFAULT_MESSAGE, help="texte du post")
    parser.add_argument("--dry-run", action="store_true", help="force shadow mode")
    args = parser.parse_args()
    return asyncio.run(run(args.message, args.dry_run))


if __name__ == "__main__":
    sys.exit(main())
