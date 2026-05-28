"""OAuth helper LinkedIn App #1 — profil perso (Share on LinkedIn).

Flow OAuth2 authorization_code :

1. Lit ``LINKEDIN_PERSONAL_CLIENT_ID`` + ``LINKEDIN_PERSONAL_CLIENT_SECRET``
   dans ``.env.local``.
2. Lance un serveur HTTP local sur http://localhost:8000/callback.
3. Ouvre le navigateur sur la page d'autorisation LinkedIn.
4. Capture le ``code`` dans le callback, l'échange contre un access_token.
5. Affiche le token + l'URN du profil perso (à copier dans ``.env.local``).

Prérequis côté LinkedIn Developer Portal (App #1) :
    - Onglet **Auth** → Authorized redirect URLs → ajouter :
      ``http://localhost:8000/callback``
    - Onglet **Products** → activer **"Sign In with LinkedIn using OpenID Connect"**
      et **"Share on LinkedIn"**.

Scopes demandés :
    - ``openid profile email`` (Sign In v2 / OIDC)
    - ``w_member_social`` (poster sur ton profil perso)

Usage :
    uv run python scripts/oauth_linkedin_personal.py
"""

from __future__ import annotations

import http.server
import os
import re
import secrets
import sys
import threading
import urllib.parse
import webbrowser
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv

# Windows console (cp1252) crash sur emojis / accents → force UTF-8.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]

REDIRECT_URI = "http://localhost:8000/callback"
PORT = 8000
SCOPES = "openid profile email w_member_social"
AUTH_URL = "https://www.linkedin.com/oauth/v2/authorization"
TOKEN_URL = "https://www.linkedin.com/oauth/v2/accessToken"
USERINFO_URL = "https://api.linkedin.com/v2/userinfo"

_received: dict[str, str] = {}
_state_expected = ""


class CallbackHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path != "/callback":
            self.send_response(404)
            self.end_headers()
            return
        params = urllib.parse.parse_qs(parsed.query)
        code = params.get("code", [""])[0]
        state = params.get("state", [""])[0]
        error = params.get("error", [""])[0]

        if error:
            _received["error"] = f"{error}: {params.get('error_description', [''])[0]}"
        elif state != _state_expected:
            _received["error"] = f"state mismatch (csrf): got {state!r}"
        elif not code:
            _received["error"] = "no code in callback"
        else:
            _received["code"] = code

        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        body = (
            "<h1>Argos Ops — OAuth callback reçu</h1>"
            "<p>Tu peux fermer cet onglet et revenir au terminal.</p>"
        )
        self.wfile.write(body.encode("utf-8"))

    def log_message(self, fmt: str, *args: Any) -> None:
        return  # silence stdout


def exchange_code_for_token(
    code: str, client_id: str, client_secret: str
) -> dict[str, Any]:
    response = httpx.post(
        TOKEN_URL,
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": REDIRECT_URI,
            "client_id": client_id,
            "client_secret": client_secret,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=15.0,
    )
    response.raise_for_status()
    return response.json()


def patch_env_local(updates: dict[str, str], env_path: Path = Path(".env.local")) -> None:
    """Remplace ou append des KEY=VALUE dans .env.local. Pas de stdout du token."""
    lines = env_path.read_text(encoding="utf-8").splitlines() if env_path.exists() else []
    handled: set[str] = set()
    for i, line in enumerate(lines):
        for key, value in updates.items():
            if re.match(rf"^\s*{re.escape(key)}\s*=", line):
                lines[i] = f"{key}={value}"
                handled.add(key)
                break
    for key, value in updates.items():
        if key not in handled:
            lines.append(f"{key}={value}")
    env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def fetch_userinfo(access_token: str) -> dict[str, Any]:
    response = httpx.get(
        USERINFO_URL,
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=15.0,
    )
    response.raise_for_status()
    return response.json()


def main() -> int:
    global _state_expected
    load_dotenv(".env.local")
    client_id = os.environ.get("LINKEDIN_PERSONAL_CLIENT_ID", "").strip()
    client_secret = os.environ.get("LINKEDIN_PERSONAL_CLIENT_SECRET", "").strip()

    if not client_id:
        print("FAIL — LINKEDIN_PERSONAL_CLIENT_ID manquant dans .env.local")
        return 1
    if not client_secret:
        print("FAIL — LINKEDIN_PERSONAL_CLIENT_SECRET manquant dans .env.local")
        print("       → LinkedIn Developer Portal → App #1 → Auth → Client Secret")
        return 1

    _state_expected = secrets.token_urlsafe(24)
    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": REDIRECT_URI,
        "state": _state_expected,
        "scope": SCOPES,
    }
    auth_url = f"{AUTH_URL}?{urllib.parse.urlencode(params)}"

    server = http.server.HTTPServer(("127.0.0.1", PORT), CallbackHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()

    print(f"[+] Serveur callback : {REDIRECT_URI}")
    print(f"[+] Scopes : {SCOPES}")
    print("[+] Ouverture du navigateur sur LinkedIn…")
    print(f"    (si rien ne s'ouvre, colle ce lien : {auth_url})\n")
    webbrowser.open(auth_url)

    print("[…] Attente du callback (timeout 300s)…")
    import time

    deadline = time.time() + 300
    while time.time() < deadline and not _received:
        time.sleep(0.5)

    server.shutdown()

    if not _received:
        print("FAIL — timeout, pas de callback reçu")
        return 2
    if "error" in _received:
        print(f"FAIL — {_received['error']}")
        return 3

    code = _received["code"]
    print("[+] Code reçu, échange contre access_token…")
    try:
        token_data = exchange_code_for_token(code, client_id, client_secret)
    except httpx.HTTPStatusError as exc:
        print(f"FAIL — exchange : HTTP {exc.response.status_code} {exc.response.text[:300]}")
        return 4

    access_token = token_data.get("access_token", "")
    expires_in = token_data.get("expires_in", 0)
    if not access_token:
        print(f"FAIL — pas d'access_token dans la réponse : {token_data}")
        return 5

    print(f"[OK] access_token reçu (len={len(access_token)}, expires_in={expires_in}s)")

    print("[+] Récupération de l'URN profil via /v2/userinfo…")
    try:
        info = fetch_userinfo(access_token)
    except httpx.HTTPStatusError as exc:
        print(f"WARN — userinfo : HTTP {exc.response.status_code} {exc.response.text[:200]}")
        info = {}

    sub = info.get("sub", "")
    name = info.get("name", "")
    person_urn = f"urn:li:person:{sub}" if sub else "(à récupérer manuellement)"

    updates = {"LINKEDIN_PERSONAL_ACCESS_TOKEN": access_token}
    if person_urn.startswith("urn:li:person:"):
        updates["LINKEDIN_PERSONAL_URN"] = person_urn
    patch_env_local(updates)

    print("\n" + "=" * 70)
    print("[OK] OAUTH PERSONNEL OK -- token ecrit dans .env.local (jamais affiche)")
    print("=" * 70)
    print(f"  - Profil       : {name or '(inconnu)'}")
    print(f"  - URN          : {person_urn}")
    print(f"  - Token len    : {len(access_token)} chars")
    print(f"  - Expires in   : {expires_in // 86400}j ({expires_in}s)")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
