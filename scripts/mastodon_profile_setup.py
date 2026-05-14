"""One-shot — setup le profil Mastodon @argos_omnividens@infosec.exchange.

Configure display_name, bio, bot flag (transparence requise par règles
serveur). Ne poste rien. Idempotent — relancer ne casse rien.

Usage : uv run python scripts/mastodon_profile_setup.py [--dry-run]
"""

from __future__ import annotations

import argparse
import os
import sys

from dotenv import load_dotenv
from mastodon import Mastodon

DISPLAY_NAME = "Omnividens"
BIO = (
    "Argos — DAST pentest BtoB. On scanne, vous corrigez.\n"
    "Pas de finding sans oracle. Bot annoncé (compte officiel Omnividens).\n"
    "https://omnividens.fr"
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Affiche sans envoyer")
    args = parser.parse_args()

    load_dotenv(".env.local")
    instance_url = os.environ.get("MASTODON_INSTANCE_URL", "").strip()
    token = os.environ.get("MASTODON_ACCESS_TOKEN", "").strip()

    if not instance_url or not token:
        print("FAIL — MASTODON_INSTANCE_URL / MASTODON_ACCESS_TOKEN manquant")
        return 1

    client = Mastodon(access_token=token, api_base_url=instance_url)
    me = client.account_verify_credentials()

    print(f"[+] Compte    : @{me['username']}@{instance_url.replace('https://', '')}")
    print(f"[+] Actuel    : display_name={me['display_name']!r} bot={me['bot']}")
    print(f"[+] Note len  : {len(me.get('source', {}).get('note') or me.get('note') or '')} chars")

    print("\n[+] Cible :")
    print(f"  display_name : {DISPLAY_NAME!r}")
    print("  bot          : True")
    print("  note         :")
    for line in BIO.splitlines():
        print(f"    | {line}")

    if args.dry_run:
        print("\n[DRY-RUN] Rien envoyé.")
        return 0

    updated = client.account_update_credentials(
        display_name=DISPLAY_NAME,
        note=BIO,
        bot=True,
    )
    print("\n[OK] Profil mis à jour")
    print(f"  display_name : {updated['display_name']!r}")
    print(f"  bot          : {updated['bot']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
