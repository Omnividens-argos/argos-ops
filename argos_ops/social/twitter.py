"""Connecteur X (ex-Twitter) — post via l'API v2 (Sprint contenu).

Publie un tweet : ``POST /2/tweets`` avec ``{"text": ...}`` et un token
**user-context** (OAuth 2.0, scope ``tweet.write``) en Bearer. L'app-only
bearer ne suffit PAS pour publier — il faut un access token utilisateur.

Mode **draft-only** : tant que ``X_ACCESS_TOKEN`` est absent, le client
opère en shadow (même contrat que les autres connecteurs). Le fondateur
arbitrera Free vs Basic ($) avant tout passage live — d'ici là on ne fait
que drafter.

> Limite connue : un access token OAuth 2.0 X expire (~2 h) et demande un
> refresh token pour être renouvelé. Comme ce canal est draft-only et son
> activation reportée, on garde le connecteur minimal (Bearer statique) ;
> la gestion du refresh (ou un OAuth 1.0a sans expiration) sera ajoutée si
> et quand le canal passe live.

Pas de pattern loguru dédié : les tokens X n'ont pas de préfixe distinctif
fiable (un filtre large ferait des faux positifs). On s'appuie sur
``SecretStr`` (jamais stringifié) + le log d'erreur structuré (jamais le
corps brut), donc le token ne transite par aucune ligne de log.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import httpx
from loguru import logger
from pydantic import SecretStr

# Limite d'un tweet en tier gratuit / standard (le premium long-post n'est
# pas dans le périmètre). Le skill/script borne en amont.
MAX_CHARS = 280


@dataclass
class TwitterClient:
    """Wrapper minimal X API v2 — publication d'un tweet."""

    access_token: SecretStr | None  # OAuth 2.0 user-context, scope tweet.write
    api_base: str = field(default="https://api.twitter.com")

    @property
    def is_live(self) -> bool:
        return self.access_token is not None

    async def post(self, text: str, *, dry_run: bool = False) -> dict[str, object]:
        """Publie ``text`` sur X. Shadow si credentials absents."""
        if dry_run or not self.is_live:
            logger.info(f"X shadow — len={len(text)} (no API call)")
            return {"status": "shadow", "platform": "x", "url": None, "error": None}

        token = self.access_token.get_secret_value() if self.access_token else ""
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                response = await client.post(
                    f"{self.api_base.rstrip('/')}/2/tweets",
                    json={"text": text},
                    headers=headers,
                )
            except httpx.HTTPError as exc:
                logger.error(f"X POST échec réseau : {exc}")
                return {"status": "failed", "platform": "x", "url": None, "error": str(exc)}

        if response.status_code >= 300:
            # X v2 renvoie soit {"detail","title","status"}, soit {"errors":[...]}.
            # On extrait un message lisible sans logger le corps brut.
            detail = ""
            try:
                body = response.json()
                if isinstance(body, dict):
                    detail = str(body.get("detail") or body.get("title") or "")
            except ValueError:
                detail = ""
            logger.error(f"X API {response.status_code} : {detail}")
            error_msg = f"HTTP {response.status_code}"
            if detail:
                error_msg = f"{error_msg}: {detail}"
            return {"status": "failed", "platform": "x", "url": None, "error": error_msg}

        data = response.json().get("data", {})
        tweet_id = data.get("id") if isinstance(data, dict) else None
        url = (
            f"https://x.com/i/web/status/{tweet_id}"
            if isinstance(tweet_id, str) and tweet_id
            else None
        )
        return {"status": "published", "platform": "x", "url": url, "error": None}


__all__ = ["MAX_CHARS", "TwitterClient"]
