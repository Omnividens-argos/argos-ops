"""Connecteur Mastodon API — toot organique (P11).

Mastodon API v1 : ``POST /api/v1/statuses``. Token créé dans
Settings → Development sur l'instance. D-025 fixe l'instance par défaut
à ``infosec.exchange`` (audience cyber). Override via env si besoin.
"""

from __future__ import annotations

from dataclasses import dataclass

import httpx
from loguru import logger
from pydantic import SecretStr


@dataclass
class MastodonClient:
    """Wrapper minimal Mastodon statuses API."""

    instance_url: str  # ex : "https://infosec.exchange"
    access_token: SecretStr | None

    @property
    def is_live(self) -> bool:
        return self.access_token is not None

    async def post(self, text: str, *, dry_run: bool = False) -> dict[str, object]:
        """Toote ``text`` sur l'instance. Shadow si token absent."""
        if dry_run or not self.is_live:
            logger.info(f"Mastodon shadow — len={len(text)} (no API call)")
            return {"status": "shadow", "platform": "mastodon", "url": None, "error": None}

        token = self.access_token.get_secret_value() if self.access_token else ""
        headers = {"Authorization": f"Bearer {token}"}
        payload = {"status": text, "visibility": "public"}

        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                response = await client.post(
                    f"{self.instance_url.rstrip('/')}/api/v1/statuses",
                    json=payload,
                    headers=headers,
                )
            except httpx.HTTPError as exc:
                logger.error(f"Mastodon POST échec réseau : {exc}")
                return {
                    "status": "failed",
                    "platform": "mastodon",
                    "url": None,
                    "error": str(exc),
                }

        if response.status_code >= 300:
            logger.error(f"Mastodon API {response.status_code} : {response.text[:200]}")
            return {
                "status": "failed",
                "platform": "mastodon",
                "url": None,
                "error": f"HTTP {response.status_code}",
            }

        data = response.json()
        return {
            "status": "published",
            "platform": "mastodon",
            "url": data.get("url"),
            "error": None,
        }


__all__ = ["MastodonClient"]
