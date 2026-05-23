"""Connecteur LinkedIn API — publication post organique (P11).

Endpoint utilisé : ``POST /v2/ugcPosts`` (LinkedIn Marketing API).
Tant que ``LINKEDIN_API_TOKEN`` n'est pas configuré dans .env, le client
opère en shadow mode (retourne un PublishResult sans appel HTTP) — D-024.

Pas de retry automatique ici : LinkedIn rate-limit à ~100 posts/jour/org,
on n'a pas besoin de hammer.
"""

from __future__ import annotations

from dataclasses import dataclass

import httpx
from loguru import logger
from pydantic import SecretStr


@dataclass
class LinkedInClient:
    """Wrapper minimal LinkedIn UGC Posts API."""

    api_token: SecretStr | None
    org_urn: str | None  # ex : "urn:li:organization:12345"
    api_base: str = "https://api.linkedin.com"

    @property
    def is_live(self) -> bool:
        return self.api_token is not None and self.org_urn is not None

    async def post(self, text: str, *, dry_run: bool = False) -> dict[str, object]:
        """Publie ``text`` sur la page LinkedIn org. Shadow si pas configuré."""
        if dry_run or not self.is_live:
            logger.info(f"LinkedIn shadow — len={len(text)} (no API call)")
            return {"status": "shadow", "platform": "linkedin", "url": None, "error": None}

        token = self.api_token.get_secret_value() if self.api_token else ""
        payload = {
            "author": self.org_urn,
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {"text": text},
                    "shareMediaCategory": "NONE",
                }
            },
            "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"},
        }
        headers = {
            "Authorization": f"Bearer {token}",
            "X-Restli-Protocol-Version": "2.0.0",
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                response = await client.post(
                    f"{self.api_base}/v2/ugcPosts", json=payload, headers=headers
                )
            except httpx.HTTPError as exc:
                logger.error(f"LinkedIn POST échec réseau : {exc}")
                return {
                    "status": "failed",
                    "platform": "linkedin",
                    "url": None,
                    "error": str(exc),
                }

        if response.status_code >= 300:
            logger.error(f"LinkedIn API {response.status_code} : {response.text[:200]}")
            return {
                "status": "failed",
                "platform": "linkedin",
                "url": None,
                "error": f"HTTP {response.status_code}",
            }

        post_id = response.headers.get("x-restli-id") or response.json().get("id")
        url = f"https://www.linkedin.com/feed/update/{post_id}" if post_id else None
        return {"status": "published", "platform": "linkedin", "url": url, "error": None}


__all__ = ["LinkedInClient"]
