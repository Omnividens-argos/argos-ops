"""OAuth helper LinkedIn App #2 — Page Omnividens (Community Management API).

Flow OAuth2 authorization_code pour obtenir un token capable de poster sur
la Page LinkedIn Omnividens via l'API ``/v2/ugcPosts`` avec author=org URN.

Prérequis côté LinkedIn Developer Portal (App #2 "Argos Ops Page") :
    - Onglet **Auth** → Authorized redirect URLs → ajouter :
      ``http://localhost:8000/callback``
    - Onglet **Products** → activer **"Community Management API"**
      (review ~3-7j parfois, sinon instantané) et **"Sign In with LinkedIn"**.
    - L'utilisateur qui lance l'OAuth doit être **Admin de la Page**
      Omnividens, sinon les scopes org seront refusés.

Scopes demandés :
    - ``openid profile email`` (Sign In / identifier l'admin)
    - ``w_organization_social`` (poster sur la Page)
    - ``r_organization_social`` (lire les posts de la Page)
    - ``rw_organization_admin`` (gérer la Page — utile pour lire les
      analytics futures)

Usage :
    uv run python scripts/oauth_linkedin_page.py
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
SCOPES = (
    "openid profile email "
    "w_organization_social r_organization_social rw_organization_admin"
)
AUTH_URL = "https://www.linkedin.com/oauth/v2/authorization"
TOKEN_URL = "https://www.linkedin.com/oauth/v2/accessToken"
ORG_ACLS_URL = "https://api.linkedin.com/v2/organizationAcls"

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
            "<h1>Argos Ops — OAuth callback Page reçu</h1>"
            "<p>Tu peux fermer cet onglet et revenir au terminal.</p>"
        )
        self.wfile.write(body.encode("utf-8"))

    def log_message(self, fmt: str, *args: Any) -> None:
        return


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


def fetch_admin_orgs(access_token: str) -> list[dict[str, Any]]:
    """Retourne les pages dont l'utilisateur est ADMINISTRATOR."""
    response = httpx.get(
        ORG_ACLS_URL,
        params={
            "q": "roleAssignee",
            "role": "ADMINISTRATOR",
            "state": "APPROVED",
        },
        headers={
            "Authorization": f"Bearer {access_token}",
            "X-Restli-Protocol-Version": "2.0.0",
        },
        timeout=15.0,
    )
    response.raise_for_status()
    return response.json().get("elements", [])


def main() -> int:
    global _state_expected
    load_dotenv(".env.local")
    client_id = os.environ.get("LINKEDIN_PAGE_CLIENT_ID", "").strip()
    client_secret = os.environ.get("LINKEDIN_PAGE_CLIENT_SECRET", "").strip()

    if not client_id:
        print("FAIL — LINKEDIN_PAGE_CLIENT_ID manquant dans .env.local")
        return 1
    if not client_secret:
        print("FAIL — LINKEDIN_PAGE_CLIENT_SECRET manquant dans .env.local")
        print("       → LinkedIn Developer Portal → App #2 → Auth → Client Secret")
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
    print("[+] Ouverture du navigateur sur LinkedIn...")
    print("    [!] Connecte-toi avec un compte ADMIN de la Page Omnividens.")
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

    print("[+] Récupération des Pages admin via /v2/organizationAcls…")
    try:
        orgs = fetch_admin_orgs(access_token)
    except httpx.HTTPStatusError as exc:
        print(f"WARN — organizationAcls : HTTP {exc.response.status_code} {exc.response.text[:200]}")
        print("       (vérifie que Community Management API est bien approuvée)")
        orgs = []

    page_urn = ""
    if orgs:
        print(f"[+] {len(orgs)} Page(s) admin trouvée(s) :")
        for org in orgs:
            org_urn = org.get("organization", "")
            print(f"    - {org_urn} (role={org.get('role')}, state={org.get('state')})")
        page_urn = orgs[0].get("organization", "")
    else:
        page_urn = "(à récupérer manuellement)"

    updates = {"LINKEDIN_PAGE_ACCESS_TOKEN": access_token}
    if page_urn.startswith("urn:li:organization:"):
        updates["LINKEDIN_PAGE_URN"] = page_urn
        updates["LINKEDIN_PAGE_ID"] = page_urn.replace("urn:li:organization:", "")
    patch_env_local(updates)

    print("\n" + "=" * 70)
    print("[OK] OAUTH PAGE OK -- token ecrit dans .env.local (jamais affiche)")
    print("=" * 70)
    print(f"  - Pages admin  : {len(orgs)}")
    print(f"  - URN choisi   : {page_urn}")
    print(f"  - Token len    : {len(access_token)} chars")
    print(f"  - Expires in   : {expires_in // 86400}j ({expires_in}s)")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
