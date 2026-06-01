"""Test live d'un post Facebook Page via MetaClient (le client de prod).

Usage :
    uv run python scripts/test_meta.py
    uv run python scripts/test_meta.py --message "texte custom"
    uv run python scripts/test_meta.py --dry-run   # shadow, ne poste pas

Si META_PAGE_ID ou META_PAGE_ACCESS_TOKEN manque dans .env.local, le client
retombe en shadow mode — utile pour valider le branchement sans rien publier.
Setup : Meta Business Suite (token de Page, scope pages_manage_posts).

Sortie : URL du post publié si succès, code retour non-zéro sinon.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys

from dotenv import load_dotenv
from pydantic import SecretStr

from argos_ops.social.meta import MetaClient

DEFAULT_MESSAGE = (
    "Test de connexion API Argos Ops — ignorez ce post. "
    "Savoir si votre site est bien protégé, c'est simple. https://omnividens.fr"
)


async def run(message: str, dry_run: bool) -> int:
    load_dotenv(".env.local")
    page_id = os.environ.get("META_PAGE_ID", "").strip()
    token = os.environ.get("META_PAGE_ACCESS_TOKEN", "").strip()
    api_version = os.environ.get("META_GRAPH_API_VERSION", "v21.0").strip()

    client = MetaClient(
        page_id=page_id or None,
        page_access_token=SecretStr(token) if token else None,
        api_version=api_version or "v21.0",
    )
    mode = "LIVE" if client.is_live and not dry_run else "SHADOW"
    print(f"[+] Page ID   : {page_id or '(absent)'}")
    print(f"[+] API ver   : {api_version}")
    print(f"[+] Mode      : {mode}")
    print(f"[+] Message   : {message}")
    print(f"[+] Longueur  : {len(message)} chars")

    if mode == "SHADOW" and not dry_run:
        print(
            "[i] Credentials Meta absents — rien posté. "
            "Remplir META_PAGE_ID + META_PAGE_ACCESS_TOKEN dans .env.local "
            "(Meta Business Suite, token de Page) pour un test live."
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
