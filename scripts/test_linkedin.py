"""Test live d'un post LinkedIn via LinkedInClient (le client de prod).

Usage :
    uv run python scripts/test_linkedin.py                  # perso par défaut
    uv run python scripts/test_linkedin.py --target page    # Page Omnividens (si CMA approuvée)
    uv run python scripts/test_linkedin.py --message "texte custom"
    uv run python scripts/test_linkedin.py --dry-run        # shadow, ne poste pas

Si les credentials de la cible demandée sont absents de .env.local, le
client retombe automatiquement en shadow mode — utile pour tester sans
risque.

Sortie : URL du post si succès, code retour non-zéro sinon. Le token
n'apparaît jamais dans stdout.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys

# Windows console (cp1252) — force UTF-8 pour éviter les crashs d'affichage.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]

from dotenv import load_dotenv
from pydantic import SecretStr

from argos_ops.social.linkedin import LinkedInClient, Target

DEFAULT_MESSAGE = (
    "Test de connexion API Argos Ops — ignorez ce post. "
    "Argos par Omnividens : on scanne, vous corrigez. "
    "https://omnividens.fr"
)


async def run(message: str, dry_run: bool, target: Target) -> int:
    load_dotenv(".env.local")

    personal_token = os.environ.get("LINKEDIN_PERSONAL_ACCESS_TOKEN", "").strip()
    personal_urn = os.environ.get("LINKEDIN_PERSONAL_URN", "").strip()
    page_token = os.environ.get("LINKEDIN_PAGE_ACCESS_TOKEN", "").strip()
    page_urn = os.environ.get("LINKEDIN_PAGE_URN", "").strip()

    client = LinkedInClient(
        personal_token=SecretStr(personal_token) if personal_token else None,
        personal_urn=personal_urn or None,
        page_token=SecretStr(page_token) if page_token else None,
        page_urn=page_urn or None,
    )

    print(f"[+] Cible demandée : {target}")
    print(f"[+] Perso live ?   : {client.personal_is_live}")
    print(f"[+] Page  live ?   : {client.page_is_live}")
    print(f"[+] Message        : {message}")
    print(f"[+] Longueur       : {len(message)} chars (max ~3000 sur LinkedIn)")

    if len(message) > 3000:
        print("FAIL — message > 3000 chars")
        return 2

    result = await client.post(message, dry_run=dry_run, target=target)
    status = result.get("status")
    url = result.get("url")
    error = result.get("error")
    resolved = result.get("target")

    if status == "published":
        print(f"[OK] Publié sur {resolved} — URL : {url}")
        return 0
    if status == "shadow":
        print(
            f"[OK] Shadow ({resolved}) — rien posté "
            "(credentials manquants ou --dry-run)."
        )
        return 0
    print(f"FAIL — status={status} target={resolved} error={error}")
    return 3


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--message", default=DEFAULT_MESSAGE, help="texte du post")
    parser.add_argument("--dry-run", action="store_true", help="force shadow mode")
    parser.add_argument(
        "--target",
        choices=("personal", "page", "auto"),
        default="personal",
        help="cible : personal (App #1), page (App #2, nécessite CMA approuvée), "
        "ou auto (page si dispo, sinon perso)",
    )
    args = parser.parse_args()
    return asyncio.run(run(args.message, args.dry_run, args.target))


if __name__ == "__main__":
    sys.exit(main())
