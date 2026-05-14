"""Smoke test Mastodon credentials — P11-PREP-B.

Vérifie que MASTODON_ACCESS_TOKEN + MASTODON_INSTANCE_URL fonctionnent
en appelant /api/v1/accounts/verify_credentials. Ne poste rien.
Ne logge JAMAIS le token (juste username + counts).
"""

from __future__ import annotations

import os
import sys

from dotenv import load_dotenv
from mastodon import Mastodon, MastodonAPIError, MastodonUnauthorizedError


def main() -> int:
    load_dotenv(".env.local")

    instance_url = os.environ.get("MASTODON_INSTANCE_URL", "").strip()
    token = os.environ.get("MASTODON_ACCESS_TOKEN", "").strip()

    if not instance_url:
        print("FAIL — MASTODON_INSTANCE_URL manquant dans .env.local")
        return 1
    if not token:
        print("FAIL — MASTODON_ACCESS_TOKEN manquant dans .env.local")
        return 1

    print(f"[+] Instance : {instance_url}")
    print(f"[+] Token len : {len(token)} chars (valeur masquée)")

    try:
        client = Mastodon(access_token=token, api_base_url=instance_url)
        me = client.account_verify_credentials()
    except MastodonUnauthorizedError:
        print("FAIL — token rejeté (401 Unauthorized). Régénère-le côté Settings → Development.")
        return 2
    except MastodonAPIError as exc:
        print(f"FAIL — erreur API Mastodon : {exc}")
        return 3

    print("[OK] Credentials valides")
    print(f"  - username       : @{me['username']}@{instance_url.replace('https://', '')}")
    print(f"  - display_name   : {me['display_name'] or '(vide)'}")
    print(f"  - followers      : {me['followers_count']}")
    print(f"  - following      : {me['following_count']}")
    print(f"  - statuses       : {me['statuses_count']}")
    print(f"  - locked         : {me['locked']}")
    print(f"  - bot flag       : {me['bot']}")

    scopes_url = f"{instance_url}/oauth/token/info"
    print(f"\n[i] Pour vérifier les scopes du token : GET {scopes_url}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
