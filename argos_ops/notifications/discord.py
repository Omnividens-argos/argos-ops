"""Discord webhook outbound — embeds riches + texte simple.

Le format embed est canonique pour les digests / alertes structurées.
Le format texte est conservé pour les messages ad-hoc (ex : escalade Tier 2).

Convention couleur (hex int — Discord embed.color) :
    GREEN  = 0x2ECC71  ← tout va bien
    YELLOW = 0xF1C40F  ← attention requise (escalades en attente)
    ORANGE = 0xE67E22  ← anomalie modérée
    RED    = 0xE74C3C  ← breaker actif / erreur
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Final

import httpx
from loguru import logger
from pydantic import SecretStr

# Couleurs Discord canoniques (hex int)
GREEN: Final[int] = 0x2ECC71
YELLOW: Final[int] = 0xF1C40F
ORANGE: Final[int] = 0xE67E22
RED: Final[int] = 0xE74C3C


@dataclass
class EmbedField:
    name: str
    value: str
    inline: bool = True


@dataclass
class Embed:
    """Sous-ensemble du schéma Discord embed qu'on utilise vraiment."""

    title: str
    description: str | None = None
    color: int = GREEN
    fields: list[EmbedField] = field(default_factory=list)
    footer: str | None = None
    timestamp: str | None = None  # ISO 8601 ; Discord l'affiche en local user

    def to_payload(self) -> dict[str, object]:
        out: dict[str, object] = {"title": self.title, "color": self.color}
        if self.description:
            out["description"] = self.description
        if self.fields:
            out["fields"] = [
                {"name": f.name, "value": f.value, "inline": f.inline} for f in self.fields
            ]
        if self.footer:
            out["footer"] = {"text": self.footer}
        if self.timestamp:
            out["timestamp"] = self.timestamp
        return out


async def send_embed(webhook_url: SecretStr, embed: Embed) -> None:
    """Push un embed sur le webhook Discord. Lève une exception si HTTP != 2xx."""
    payload = {"embeds": [embed.to_payload()]}
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(webhook_url.get_secret_value(), json=payload)
        if response.status_code >= 300:
            logger.error(
                f"Discord webhook a renvoyé {response.status_code} : {response.text[:200]}"
            )
            response.raise_for_status()
    logger.debug(f"Discord embed posté : {embed.title}")


async def send_text(webhook_url: SecretStr, content: str) -> None:
    """Push un message texte simple. ``content`` ≤ 2000 caractères."""
    if len(content) > 2000:
        content = content[:1997] + "..."
    payload = {"content": content}
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(webhook_url.get_secret_value(), json=payload)
        if response.status_code >= 300:
            logger.error(
                f"Discord webhook a renvoyé {response.status_code} : {response.text[:200]}"
            )
            response.raise_for_status()


__all__ = ["GREEN", "ORANGE", "RED", "YELLOW", "Embed", "EmbedField", "send_embed", "send_text"]
