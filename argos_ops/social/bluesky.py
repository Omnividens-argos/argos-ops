"""Connecteur Bluesky API — post organique via AT Protocol (Sprint B).

Bluesky n'a pas d'API « simple » comme Mastodon : il faut d'abord ouvrir
une session (``com.atproto.server.createSession``) pour récupérer un JWT,
puis créer l'enregistrement (``com.atproto.repo.createRecord``) avec ce
JWT. Aucune clé API payante — un *app password* gratuit (illimité) suffit,
généré depuis Settings → App Passwords. C'est le quick win 100 % gratuit
du Sprint contenu.

Authentification : ``BLUESKY_HANDLE`` + ``BLUESKY_APP_PASSWORD``. Tant que
l'un des deux manque, le client opère en shadow mode (retourne un résultat
sans appel HTTP), même contrat que ``MastodonClient`` / ``LinkedInClient``.

Rich text : Bluesky n'auto-linkifie rien. Les URLs et hashtags d'un post
restent du texte mort tant qu'on n'envoie pas des *facets* (annotations
indexées en **offsets octets** UTF-8). ``_build_facets`` reconstruit ces
annotations pour que le CTA et les hashtags soient cliquables.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import UTC, datetime

import httpx
from loguru import logger
from pydantic import SecretStr

# Limite officielle d'un post Bluesky (graphemes). On compte en code points
# côté connecteur (approximation suffisante) ; le skill/script borne en amont.
MAX_GRAPHEMES = 300

# URL : http(s) jusqu'au prochain blanc ou délimiteur fermant. La ponctuation
# de fin de phrase est retirée après coup (cf. _strip_trailing_punct).
_URL_RE = re.compile(r"https?://[^\s\]\)<>]+", re.IGNORECASE)
# Hashtag précédé d'un début de ligne ou d'un blanc (évite de capturer un
# fragment d'URL `...#section`). Commence par une lettre, pas un chiffre seul.
_TAG_RE = re.compile(r"(?:^|\s)(#[A-Za-z][\w-]*)")
_TRAILING_PUNCT = ".,;:!?»\"'"


def _strip_trailing_punct(url: str) -> str:
    """Retire la ponctuation de fin collée à une URL en fin de phrase."""
    return url.rstrip(_TRAILING_PUNCT)


def _byte_len(text: str) -> int:
    return len(text.encode("utf-8"))


def _build_facets(text: str) -> list[dict[str, object]]:
    """Construit les facets AT Protocol (liens + hashtags) pour ``text``.

    Les index sont des **offsets octets** UTF-8 (``byteStart``/``byteEnd``),
    pas des offsets caractères — un emoji ou un accent décale donc les
    positions. On encode le préfixe pour obtenir chaque offset.
    """
    # On garde l'offset de départ à côté du facet pour trier ensuite sans
    # avoir à ré-indexer dans des dicts hétérogènes (mypy-friendly).
    indexed: list[tuple[int, dict[str, object]]] = []

    for match in _URL_RE.finditer(text):
        url = _strip_trailing_punct(match.group(0))
        if not url:
            continue
        start = _byte_len(text[: match.start()])
        end = start + _byte_len(url)
        indexed.append(
            (
                start,
                {
                    "index": {"byteStart": start, "byteEnd": end},
                    "features": [{"$type": "app.bsky.richtext.facet#link", "uri": url}],
                },
            )
        )

    for match in _TAG_RE.finditer(text):
        token = match.group(1)  # inclut le '#'
        tag = token[1:].rstrip(_TRAILING_PUNCT)
        if not tag:
            continue
        start = _byte_len(text[: match.start(1)])
        end = start + _byte_len(token)
        indexed.append(
            (
                start,
                {
                    "index": {"byteStart": start, "byteEnd": end},
                    "features": [{"$type": "app.bsky.richtext.facet#tag", "tag": tag}],
                },
            )
        )

    indexed.sort(key=lambda pair: pair[0])
    return [facet for _, facet in indexed]


@dataclass
class BlueskyClient:
    """Wrapper minimal AT Protocol — createSession puis createRecord."""

    handle: str | None  # ex : "omnividens.bsky.social"
    app_password: SecretStr | None
    pds_url: str = field(default="https://bsky.social")

    @property
    def is_live(self) -> bool:
        return self.handle is not None and self.app_password is not None

    def _base(self) -> str:
        return self.pds_url.rstrip("/")

    async def _create_session(self, client: httpx.AsyncClient) -> tuple[str, str] | None:
        """Ouvre une session. Retourne ``(access_jwt, did)`` ou ``None``."""
        password = self.app_password.get_secret_value() if self.app_password else ""
        try:
            response = await client.post(
                f"{self._base()}/xrpc/com.atproto.server.createSession",
                json={"identifier": self.handle, "password": password},
            )
        except httpx.HTTPError as exc:
            logger.error(f"Bluesky createSession échec réseau : {exc}")
            return None
        if response.status_code >= 300:
            logger.error(f"Bluesky createSession {response.status_code} : {response.text[:200]}")
            return None
        data = response.json()
        jwt = data.get("accessJwt")
        did = data.get("did")
        if not isinstance(jwt, str) or not isinstance(did, str):
            logger.error("Bluesky createSession : accessJwt/did manquant")
            return None
        return jwt, did

    def _post_url(self, did: str, uri: str | None) -> str | None:
        """Transforme un ``at://`` URI en permalink bsky.app cliquable."""
        if not uri:
            return None
        rkey = uri.rsplit("/", 1)[-1]
        handle = self.handle or did
        return f"https://bsky.app/profile/{handle}/post/{rkey}"

    async def post(self, text: str, *, dry_run: bool = False) -> dict[str, object]:
        """Publie ``text`` sur Bluesky. Shadow si credentials absents."""
        if dry_run or not self.is_live:
            logger.info(f"Bluesky shadow — len={len(text)} (no API call)")
            return {"status": "shadow", "platform": "bluesky", "url": None, "error": None}

        record: dict[str, object] = {
            "$type": "app.bsky.feed.post",
            "text": text,
            "createdAt": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "langs": ["fr"],
        }
        facets = _build_facets(text)
        if facets:
            record["facets"] = facets

        async with httpx.AsyncClient(timeout=15.0) as client:
            session = await self._create_session(client)
            if session is None:
                return {
                    "status": "failed",
                    "platform": "bluesky",
                    "url": None,
                    "error": "createSession failed",
                }
            access_jwt, did = session
            try:
                response = await client.post(
                    f"{self._base()}/xrpc/com.atproto.repo.createRecord",
                    json={
                        "repo": did,
                        "collection": "app.bsky.feed.post",
                        "record": record,
                    },
                    headers={"Authorization": f"Bearer {access_jwt}"},
                )
            except httpx.HTTPError as exc:
                logger.error(f"Bluesky createRecord échec réseau : {exc}")
                return {
                    "status": "failed",
                    "platform": "bluesky",
                    "url": None,
                    "error": str(exc),
                }

        if response.status_code >= 300:
            logger.error(f"Bluesky createRecord {response.status_code} : {response.text[:200]}")
            return {
                "status": "failed",
                "platform": "bluesky",
                "url": None,
                "error": f"HTTP {response.status_code}",
            }

        uri = response.json().get("uri")
        return {
            "status": "published",
            "platform": "bluesky",
            "url": self._post_url(did, uri if isinstance(uri, str) else None),
            "error": None,
        }


__all__ = ["MAX_GRAPHEMES", "BlueskyClient", "_build_facets"]
