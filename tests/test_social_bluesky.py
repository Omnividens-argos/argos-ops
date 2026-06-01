"""Tests unitaires de :mod:`argos_ops.social.bluesky` (Sprint B).

Deux familles :

- ``_build_facets`` — fonction pure, aucun réseau. On vérifie surtout que
  les offsets sont bien en **octets** UTF-8 (un accent décale tout) et que
  la ponctuation de fin d'URL est retirée.
- ``BlueskyClient.post`` — flux à deux appels (createSession puis
  createRecord). On mocke ``httpx.AsyncClient`` avec un faux client qui
  route la réponse selon l'URL et enregistre les requêtes envoyées, pour
  asserter le payload (texte, facets, header Authorization).
"""

from __future__ import annotations

from typing import Any

import httpx
import pytest
from pydantic import SecretStr

from argos_ops.social import bluesky
from argos_ops.social.bluesky import MAX_GRAPHEMES, BlueskyClient, _build_facets

# --------------------------------------------------------------------------
# Faux httpx.AsyncClient
# --------------------------------------------------------------------------


class _FakeResponse:
    def __init__(self, status_code: int, json_data: dict[str, Any] | None = None, text: str = ""):
        self.status_code = status_code
        self._json = json_data or {}
        self.text = text
        self.headers: dict[str, str] = {}

    def json(self) -> dict[str, Any]:
        return self._json


def _fake_client_factory(
    routes: list[tuple[str, _FakeResponse | Exception]],
    recorder: list[dict[str, Any]],
) -> type:
    """Construit une classe AsyncClient factice routant par substring d'URL."""

    class _FakeAsyncClient:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass

        async def __aenter__(self) -> _FakeAsyncClient:
            return self

        async def __aexit__(self, *exc: Any) -> bool:
            return False

        async def post(
            self,
            url: str,
            *,
            json: dict[str, Any] | None = None,
            headers: dict[str, str] | None = None,
        ) -> _FakeResponse:
            recorder.append({"url": url, "json": json, "headers": headers})
            for key, resp in routes:
                if key in url:
                    if isinstance(resp, Exception):
                        raise resp
                    return resp
            raise AssertionError(f"URL inattendue: {url}")

    return _FakeAsyncClient


def _patch_client(
    monkeypatch: pytest.MonkeyPatch,
    routes: list[tuple[str, _FakeResponse | Exception]],
) -> list[dict[str, Any]]:
    recorder: list[dict[str, Any]] = []
    monkeypatch.setattr(bluesky.httpx, "AsyncClient", _fake_client_factory(routes, recorder))
    return recorder


def _live_client() -> BlueskyClient:
    return BlueskyClient(handle="omnividens.bsky.social", app_password=SecretStr("app-pw-1234"))


# --------------------------------------------------------------------------
# _build_facets — offsets octets
# --------------------------------------------------------------------------


def test_build_facets_empty_on_plain_text() -> None:
    assert _build_facets("juste du texte sans lien ni tag") == []


def test_build_facets_link_byte_offsets() -> None:
    text = "Voir https://omnividens.fr ici"
    facets = _build_facets(text)
    assert len(facets) == 1
    facet = facets[0]
    feature = facet["features"][0]  # type: ignore[index]
    assert feature["$type"] == "app.bsky.richtext.facet#link"
    assert feature["uri"] == "https://omnividens.fr"
    # "Voir " = 5 octets ASCII ; "https://omnividens.fr" = 21 octets
    assert facet["index"]["byteStart"] == 5  # type: ignore[index]
    assert facet["index"]["byteEnd"] == 26  # type: ignore[index]


def test_build_facets_strips_trailing_punctuation_from_url() -> None:
    text = "Lire https://omnividens.fr."
    facet = _build_facets(text)[0]
    assert facet["features"][0]["uri"] == "https://omnividens.fr"  # type: ignore[index]
    # le '.' final est hors de l'URL : byteEnd s'arrête à "...fr" (5 + 21)
    assert facet["index"]["byteEnd"] == 26  # type: ignore[index]


def test_build_facets_tag_uses_byte_offsets_with_accents() -> None:
    # "é" et "è" pèsent 2 octets chacun : l'offset octet du '#' (8) diffère
    # de son offset caractère (6).
    text = "Décès #infosec"
    facet = _build_facets(text)[0]
    feature = facet["features"][0]  # type: ignore[index]
    assert feature["$type"] == "app.bsky.richtext.facet#tag"
    assert feature["tag"] == "infosec"  # sans le '#'
    # "Décès " = 8 octets (é, è = 2 octets) alors que c'est 6 caractères :
    # l'offset octet du '#' (8) prouve qu'on n'utilise pas l'offset caractère.
    assert facet["index"]["byteStart"] == 8  # type: ignore[index]
    assert facet["index"]["byteEnd"] == 16  # 8 + len("#infosec") == 8  # type: ignore[index]


def test_build_facets_ignores_url_fragment_as_tag() -> None:
    # Un '#fragment' collé à une URL (précédé de '/') ne doit pas devenir un
    # tag : seul le lien est annoté.
    facets = _build_facets("https://example.com/#section")
    assert len(facets) == 1
    assert facets[0]["features"][0]["$type"] == "app.bsky.richtext.facet#link"  # type: ignore[index]


def test_build_facets_sorted_by_byte_start() -> None:
    facets = _build_facets("#alpha puis https://omnividens.fr enfin #beta")
    starts = [f["index"]["byteStart"] for f in facets]  # type: ignore[index]
    assert starts == sorted(starts)
    assert len(facets) == 3


def test_build_facets_emoji_4byte_offsets() -> None:
    # 🔥 = 4 octets (caractère astral) : décale tout de 3 octets vs l'offset
    # caractère. C'est le cas que les accents 2-octets ne couvrent pas, et le
    # style de contenu (hook punchy) peut contenir des emoji.
    facets = _build_facets("🔥 https://omnividens.fr #infosec")
    link, tag = facets[0], facets[1]
    assert link["features"][0]["$type"] == "app.bsky.richtext.facet#link"  # type: ignore[index]
    assert link["index"]["byteStart"] == 5  # 🔥(4) + espace(1)  # type: ignore[index]
    assert link["index"]["byteEnd"] == 26  # 5 + 21  # type: ignore[index]
    assert tag["features"][0]["$type"] == "app.bsky.richtext.facet#tag"  # type: ignore[index]
    assert tag["index"]["byteStart"] == 27  # 26 + espace(1)  # type: ignore[index]
    assert tag["index"]["byteEnd"] == 35  # 27 + len("#infosec") == 8  # type: ignore[index]


def test_build_facets_two_links_offsets_recomputed_independently() -> None:
    facets = _build_facets("A https://a.fr et B https://b.fr fin")
    assert len(facets) == 2
    assert facets[0]["index"]["byteStart"] == 2  # type: ignore[index]
    assert (
        facets[0]["index"]["byteEnd"] == 14
    )  # 2 + len("https://a.fr") == 12  # type: ignore[index]
    assert facets[1]["index"]["byteStart"] == 20  # type: ignore[index]
    assert facets[1]["index"]["byteEnd"] == 32  # 20 + 12  # type: ignore[index]


def test_build_facets_tag_at_string_start() -> None:
    # Branche '^' de _TAG_RE : tag tout premier token, byteStart == 0.
    facet = _build_facets("#infosec au debut")[0]
    assert facet["features"][0]["$type"] == "app.bsky.richtext.facet#tag"  # type: ignore[index]
    assert facet["index"]["byteStart"] == 0  # type: ignore[index]
    assert facet["index"]["byteEnd"] == 8  # len("#infosec")  # type: ignore[index]


def test_build_facets_tag_at_string_end_lands_on_length() -> None:
    text = "lire ceci #cyber"
    facet = _build_facets(text)[0]
    assert facet["index"]["byteEnd"] == len(text.encode("utf-8"))  # 16  # type: ignore[index]


# --------------------------------------------------------------------------
# is_live
# --------------------------------------------------------------------------


def test_is_live_requires_both_handle_and_password() -> None:
    assert BlueskyClient(handle=None, app_password=SecretStr("x")).is_live is False
    assert BlueskyClient(handle="h", app_password=None).is_live is False
    assert BlueskyClient(handle="h", app_password=SecretStr("x")).is_live is True


def test_post_url_builds_permalink() -> None:
    client = _live_client()
    uri = "at://did:plc:abc/app.bsky.feed.post/3kxyz789"
    assert (
        client._post_url("did:plc:abc", uri)
        == "https://bsky.app/profile/omnividens.bsky.social/post/3kxyz789"
    )
    assert client._post_url("did:plc:abc", None) is None


# --------------------------------------------------------------------------
# post() — shadow / dry-run
# --------------------------------------------------------------------------


async def test_post_shadow_without_credentials() -> None:
    client = BlueskyClient(handle=None, app_password=None)
    result = await client.post("coucou")
    assert result["status"] == "shadow"
    assert result["platform"] == "bluesky"
    assert result["url"] is None


async def test_post_dry_run_is_shadow_even_with_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recorder = _patch_client(monkeypatch, [])
    result = await _live_client().post("texte", dry_run=True)
    assert result["status"] == "shadow"
    assert recorder == []  # aucun appel réseau


# --------------------------------------------------------------------------
# post() — chemin nominal
# --------------------------------------------------------------------------


async def test_post_published_sends_facets_and_auth(monkeypatch: pytest.MonkeyPatch) -> None:
    routes: list[tuple[str, _FakeResponse | Exception]] = [
        ("createSession", _FakeResponse(200, {"accessJwt": "JWT-TOKEN", "did": "did:plc:abc"})),
        ("createRecord", _FakeResponse(200, {"uri": "at://did:plc:abc/app.bsky.feed.post/3kabc"})),
    ]
    recorder = _patch_client(monkeypatch, routes)
    body = "On scanne, vous corrigez. https://omnividens.fr #infosec"

    result = await _live_client().post(body)

    assert result["status"] == "published"
    assert result["url"] == "https://bsky.app/profile/omnividens.bsky.social/post/3kabc"
    assert result["error"] is None

    # createSession envoie identifier + password
    session_call = next(c for c in recorder if "createSession" in c["url"])
    assert session_call["json"]["identifier"] == "omnividens.bsky.social"
    assert session_call["json"]["password"] == "app-pw-1234"

    # createRecord : texte exact + facets + collection + header Authorization
    record_call = next(c for c in recorder if "createRecord" in c["url"])
    assert record_call["headers"]["Authorization"] == "Bearer JWT-TOKEN"
    assert record_call["json"]["collection"] == "app.bsky.feed.post"
    record = record_call["json"]["record"]
    assert record["text"] == body
    assert record["$type"] == "app.bsky.feed.post"
    assert record["createdAt"].endswith("Z")
    assert record["langs"] == ["fr"]
    assert "facets" in record  # le lien + le hashtag ont produit des facets


async def test_post_omits_facets_when_plain_text(monkeypatch: pytest.MonkeyPatch) -> None:
    routes: list[tuple[str, _FakeResponse | Exception]] = [
        ("createSession", _FakeResponse(200, {"accessJwt": "J", "did": "did:plc:x"})),
        ("createRecord", _FakeResponse(200, {"uri": "at://did:plc:x/app.bsky.feed.post/1"})),
    ]
    recorder = _patch_client(monkeypatch, routes)
    await _live_client().post("texte brut sans lien ni hashtag")
    record = next(c for c in recorder if "createRecord" in c["url"])["json"]["record"]
    assert "facets" not in record


# --------------------------------------------------------------------------
# post() — échecs
# --------------------------------------------------------------------------


async def test_post_create_session_http_error_short_circuits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    routes: list[tuple[str, _FakeResponse | Exception]] = [
        ("createSession", _FakeResponse(401, {}, text="bad credentials")),
    ]
    recorder = _patch_client(monkeypatch, routes)
    result = await _live_client().post("hello")
    assert result["status"] == "failed"
    assert result["error"] == "createSession failed"
    # createRecord ne doit jamais être appelé
    assert all("createRecord" not in c["url"] for c in recorder)


async def test_post_create_session_network_error(monkeypatch: pytest.MonkeyPatch) -> None:
    routes: list[tuple[str, _FakeResponse | Exception]] = [
        ("createSession", httpx.ConnectError("boom")),
    ]
    _patch_client(monkeypatch, routes)
    result = await _live_client().post("hello")
    assert result["status"] == "failed"
    assert result["error"] == "createSession failed"


async def test_post_create_record_http_error(monkeypatch: pytest.MonkeyPatch) -> None:
    routes: list[tuple[str, _FakeResponse | Exception]] = [
        ("createSession", _FakeResponse(200, {"accessJwt": "J", "did": "did:plc:x"})),
        ("createRecord", _FakeResponse(400, {}, text="invalid record")),
    ]
    _patch_client(monkeypatch, routes)
    result = await _live_client().post("hello")
    assert result["status"] == "failed"
    assert result["error"] == "HTTP 400"


async def test_post_create_record_network_error(monkeypatch: pytest.MonkeyPatch) -> None:
    routes: list[tuple[str, _FakeResponse | Exception]] = [
        ("createSession", _FakeResponse(200, {"accessJwt": "J", "did": "did:plc:x"})),
        ("createRecord", httpx.ReadError("timeout")),
    ]
    _patch_client(monkeypatch, routes)
    result = await _live_client().post("hello")
    assert result["status"] == "failed"
    assert result["error"] == "timeout"


async def test_post_session_missing_jwt_is_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    routes: list[tuple[str, _FakeResponse | Exception]] = [
        ("createSession", _FakeResponse(200, {"did": "did:plc:x"})),  # accessJwt manquant
    ]
    _patch_client(monkeypatch, routes)
    result = await _live_client().post("hello")
    assert result["status"] == "failed"
    assert result["error"] == "createSession failed"


def test_max_graphemes_constant() -> None:
    assert MAX_GRAPHEMES == 300
