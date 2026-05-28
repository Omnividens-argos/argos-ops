"""Connecteur LinkedIn API — publication post organique (P11).

Supporte 2 cibles :

- **personal** (App #1 "Argos Ops", scope ``w_member_social``) — poste sur
  le profil perso du fondateur via author=``urn:li:person:<id>``.
- **page** (App #2 "Argos Ops Page", Community Management API) — poste
  sur la Page Omnividens via author=``urn:li:organization:<id>``.
  Activable seulement quand LinkedIn aura approuvé CMA (review > 14j
  actuellement, cf. memo project).

Endpoint dans les deux cas : ``POST /v2/ugcPosts``.

Mode shadow (pas d'appel HTTP) si :
    - ``dry_run=True``
    - ou la cible demandée n'a pas de credentials (token + URN) configurés.

Pas de retry automatique : LinkedIn rate-limit à ~100 posts/jour/auteur,
on n'a pas besoin de hammer.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import httpx
from loguru import logger
from pydantic import SecretStr

Target = Literal["personal", "page", "auto"]


@dataclass
class LinkedInClient:
    """Wrapper LinkedIn UGC Posts API supportant perso (App #1) + Page (App #2)."""

    personal_token: SecretStr | None = None
    personal_urn: str | None = None  # ex : "urn:li:person:abc123"
    page_token: SecretStr | None = None
    page_urn: str | None = None  # ex : "urn:li:organization:12345"
    api_base: str = "https://api.linkedin.com"

    @property
    def personal_is_live(self) -> bool:
        return self.personal_token is not None and bool(self.personal_urn)

    @property
    def page_is_live(self) -> bool:
        return self.page_token is not None and bool(self.page_urn)

    @property
    def is_live(self) -> bool:
        """True si au moins une cible est postable."""
        return self.personal_is_live or self.page_is_live

    def _resolve_target(self, target: Target) -> Target:
        if target != "auto":
            return target
        # Préférer Page si dispo (audience brandée), sinon perso.
        return "page" if self.page_is_live else "personal"

    async def post(
        self,
        text: str,
        *,
        dry_run: bool = False,
        target: Target = "auto",
    ) -> dict[str, object]:
        """Publie ``text`` via la cible choisie. Shadow si non configurée."""
        resolved = self._resolve_target(target)
        if resolved == "page":
            token = self.page_token
            author = self.page_urn
        else:
            token = self.personal_token
            author = self.personal_urn
            resolved = "personal"

        if dry_run or token is None or not author:
            logger.info(
                f"LinkedIn shadow ({resolved}) — len={len(text)} (no API call)"
            )
            return {
                "status": "shadow",
                "platform": "linkedin",
                "target": resolved,
                "url": None,
                "error": None,
            }

        payload = {
            "author": author,
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
            "Authorization": f"Bearer {token.get_secret_value()}",
            "X-Restli-Protocol-Version": "2.0.0",
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                response = await client.post(
                    f"{self.api_base}/v2/ugcPosts", json=payload, headers=headers
                )
            except httpx.HTTPError as exc:
                logger.error(f"LinkedIn POST ({resolved}) échec réseau : {exc}")
                return {
                    "status": "failed",
                    "platform": "linkedin",
                    "target": resolved,
                    "url": None,
                    "error": str(exc),
                }

        if response.status_code >= 300:
            logger.error(
                f"LinkedIn API ({resolved}) {response.status_code} : {response.text[:200]}"
            )
            return {
                "status": "failed",
                "platform": "linkedin",
                "target": resolved,
                "url": None,
                "error": f"HTTP {response.status_code}",
            }

        post_id = response.headers.get("x-restli-id")
        if not post_id:
            try:
                post_id = response.json().get("id")
            except ValueError:
                post_id = None
        url = (
            f"https://www.linkedin.com/feed/update/{post_id}" if post_id else None
        )
        return {
            "status": "published",
            "platform": "linkedin",
            "target": resolved,
            "url": url,
            "error": None,
        }


__all__ = ["LinkedInClient", "Target"]
