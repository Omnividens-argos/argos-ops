"""Connecteur Meta / Facebook Page — publication organique (Sprint contenu).

Publie un post texte sur une **Page Facebook** via la Graph API :
``POST /{page-id}/feed`` avec ``message`` + ``access_token`` (token de
Page long-lived, scope ``pages_manage_posts``). Cf. ``docs/META-OAUTH-SETUP.md``
pour l'obtention du token (action manuelle fondateur via Meta Business Suite).

Distinct du connecteur Ads (``META_ADS_*``) : ici c'est de l'organique
gratuit sur la Page, pas du pilotage de campagnes payantes.

Tant que ``META_PAGE_ID`` ou ``META_PAGE_ACCESS_TOKEN`` manque, le client
opère en **shadow** (mode draft-only) — même contrat que les autres
connecteurs (``MastodonClient`` / ``LinkedInClient`` / ``BlueskyClient``).

Le token part dans le **corps** de la requête (form-encoded), jamais dans
l'URL — pour éviter qu'un proxy/intermédiaire ne le logue.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import httpx
from loguru import logger
from pydantic import SecretStr


@dataclass
class MetaClient:
    """Wrapper minimal Graph API — publication sur une Page Facebook."""

    page_id: str | None  # ex : "123456789012345"
    page_access_token: SecretStr | None
    api_version: str = field(default="v21.0")
    api_base: str = field(default="https://graph.facebook.com")

    @property
    def is_live(self) -> bool:
        return self.page_id is not None and self.page_access_token is not None

    async def post(self, text: str, *, dry_run: bool = False) -> dict[str, object]:
        """Publie ``text`` sur la Page. Shadow si credentials absents."""
        if dry_run or not self.is_live:
            logger.info(f"Meta shadow — len={len(text)} (no API call)")
            return {"status": "shadow", "platform": "meta", "url": None, "error": None}

        token = self.page_access_token.get_secret_value() if self.page_access_token else ""
        url = f"{self.api_base.rstrip('/')}/{self.api_version}/{self.page_id}/feed"
        # access_token dans le body (form), pas dans l'URL.
        payload = {"message": text, "access_token": token}

        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                response = await client.post(url, data=payload)
            except httpx.HTTPError as exc:
                logger.error(f"Meta POST échec réseau : {exc}")
                return {"status": "failed", "platform": "meta", "url": None, "error": str(exc)}

        if response.status_code >= 300:
            # Graph renvoie {"error": {"message", "code", "fbtrace_id", ...}}.
            # On extrait le message structuré (qui ne contient pas le token) et
            # on évite de logger le corps brut — le token de Page ne fuite pas,
            # mais on n'a pas besoin du payload entier dans les logs.
            detail = ""
            code: object = None
            try:
                err = response.json().get("error", {})
                if isinstance(err, dict):
                    detail = str(err.get("message") or "")
                    code = err.get("code")
            except ValueError:
                detail = response.text[:120]
            suffix = f" (code {code})" if code is not None else ""
            logger.error(f"Meta API {response.status_code} : {detail}{suffix}")
            error_msg = f"HTTP {response.status_code}"
            if detail:
                error_msg = f"{error_msg}: {detail}{suffix}"
            return {
                "status": "failed",
                "platform": "meta",
                "url": None,
                "error": error_msg,
            }

        post_id = response.json().get("id")
        url_pub = (
            f"https://www.facebook.com/{post_id}" if isinstance(post_id, str) and post_id else None
        )
        return {"status": "published", "platform": "meta", "url": url_pub, "error": None}


__all__ = ["MetaClient"]
