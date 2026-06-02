"""Connecteur Truth Social — post organique (Sprint contenu).

Truth Social est un **fork de Mastodon** : l'API est la même
(``POST /api/v1/statuses`` avec ``Authorization: Bearer <token>``), seule
l'instance change (``truthsocial.com``). Le connecteur reprend donc le
contrat de ``MastodonClient``.

Mode **draft-only** : tant que ``TRUTH_SOCIAL_ACCESS_TOKEN`` est absent, le
client opère en shadow (même contrat que les autres connecteurs). L'accès
API Truth Social n'est pas ouvert librement — le fondateur doit le demander
avant tout passage live. D'ici là on ne fait que drafter.

> **Fit audience** : Truth Social est une plateforme US généraliste /
> politique, très éloignée de l'ICP Argos (CTO/RSSI de scaleups FR). C'est
> le canal **le plus expérimental** du Sprint contenu — voir le skill
> ``truth-social-writer`` pour le calibrage éditorial.

Pas de pattern loguru dédié : les tokens Truth Social (style Mastodon) n'ont
pas de préfixe distinctif fiable. On s'appuie sur ``SecretStr`` + le log
d'erreur structuré, donc le token ne transite par aucune ligne de log.
"""

from __future__ import annotations

from dataclasses import dataclass

import httpx
from loguru import logger
from pydantic import SecretStr

# Limite Mastodon-fork par défaut (Truth Social hérite du moteur Mastodon).
MAX_CHARS = 500


@dataclass
class TruthSocialClient:
    """Wrapper minimal Truth Social (API Mastodon) — publication d'un post."""

    instance_url: str  # ex : "https://truthsocial.com"
    access_token: SecretStr | None

    @property
    def is_live(self) -> bool:
        return self.access_token is not None

    async def post(self, text: str, *, dry_run: bool = False) -> dict[str, object]:
        """Publie ``text`` sur Truth Social. Shadow si token absent."""
        if dry_run or not self.is_live:
            logger.info(f"TruthSocial shadow — len={len(text)} (no API call)")
            return {"status": "shadow", "platform": "truth", "url": None, "error": None}

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
                logger.error(f"TruthSocial POST échec réseau : {exc}")
                return {"status": "failed", "platform": "truth", "url": None, "error": str(exc)}

        if response.status_code >= 300:
            # L'API Mastodon renvoie {"error": "..."} — on surface ce message
            # sans logger le corps brut.
            detail = ""
            try:
                body = response.json()
                if isinstance(body, dict):
                    detail = str(body.get("error") or "")
            except ValueError:
                detail = ""
            logger.error(f"TruthSocial API {response.status_code} : {detail}")
            error_msg = f"HTTP {response.status_code}"
            if detail:
                error_msg = f"{error_msg}: {detail}"
            return {"status": "failed", "platform": "truth", "url": None, "error": error_msg}

        url = response.json().get("url")
        return {
            "status": "published",
            "platform": "truth",
            "url": url if isinstance(url, str) else None,
            "error": None,
        }


__all__ = ["MAX_CHARS", "TruthSocialClient"]
