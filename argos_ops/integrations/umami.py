"""Client async Umami self-host — métriques landing pour LandingOptimizer.

Umami (https://umami.is) est un analytics web open-source self-hostable
(Docker, gratuit, RGPD-friendly sans cookies). Sous D-017 c'est la brique
analytics 100 % locale d'Argos Ops : aucune API SaaS tierce, le founder
héberge l'instance sur ``analytics.omnividens.fr`` (INFRA-02). Ce module
remplace l'alimentation manuelle de ``data/analytics/landing_perf.yaml``
par un pull direct de l'API.

Flux API (Umami v3, vérifié contre l'instance live) — tout en JSON :

1. ``POST /api/auth/login`` ``{username, password}`` → ``{token: <JWT>}``.
2. ``GET  /api/websites/{id}/metrics?type=path&startAt=&endAt=`` → top pages
   ``[{x: "/path", y: <pageviews>}]``. (v2 utilisait ``type=url`` ; renommé
   ``type=path`` en v3, ``type=url`` y renvoie 400.)
3. ``GET  /api/websites/{id}/stats?path=/page&startAt=&endAt=`` → totaux
   *scopés à cette page* : ``{pageviews, visitors, visits, bounces,
   totaltime}``. En v3 les valeurs sont **à plat** (``{pageviews: 42}``),
   en v2 elles étaient ``{value, prev}`` — :func:`_stat_value` gère les deux.
   ``totaltime`` est en secondes cumulées. Le filtre est ``path=`` en v3
   (``url=`` y est silencieusement ignoré → renverrait les totaux du site).
4. (optionnel) ``GET /api/websites/{id}/metrics?type=event&path=/page`` →
   compte des events ; on retient celui nommé ``conversion_event`` comme
   conversion. Sans ``conversion_event`` configuré, ``conversions=0`` (la
   proposition « CR < 1 % » de LandingOptimizer ne se déclenche donc pas
   sur une fausse hypothèse).

``startAt``/``endAt`` sont des epochs **millisecondes**.

Shadow mode : tant qu'une des 4 variables (``UMAMI_BASE_URL``,
``UMAMI_USERNAME``, ``UMAMI_PASSWORD``, ``UMAMI_WEBSITE_ID``) manque,
:attr:`UmamiClient.is_configured` est ``False`` et ``fetch_landing_metrics``
retourne ``[]`` sans aucun appel réseau — LandingOptimizer retombe alors
sur le YAML manuel. Aucune exception ne remonte : toute erreur réseau/HTTP
est logguée et donne ``[]`` (résilience > précision pour un bot best-effort).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

import httpx
from loguru import logger
from pydantic import SecretStr

if TYPE_CHECKING:
    from argos_ops.config import Settings

# Plafond de pages analysées par run — on ne veut pas itérer sur des
# centaines d'URLs (1 appel /stats par URL). Le founder n'a qu'une poignée
# de landing pertinentes ; les autres sont du bruit pour l'A/B testing.
DEFAULT_TOP_URLS = 25
# Fenêtre d'analyse par défaut : 30 j, cohérent avec la cadence A/B de
# LandingOptimizer (un test a besoin de volume pour être significatif).
DEFAULT_WINDOW_DAYS = 30
_TIMEOUT = httpx.Timeout(15.0)


@dataclass(frozen=True)
class UmamiPageMetric:
    """Métriques d'une page, normalisées pour LandingOptimizer.

    DTO **propre à la couche intégration** : on ne réutilise pas
    ``LandingMetric`` (couche agent) pour éviter un import circulaire
    (l'agent importe ce module, pas l'inverse). Les champs sont alignés 1:1
    pour une conversion triviale côté agent.
    """

    page: str
    visits: int
    conversions: int
    bounce_rate: float  # 0.0-1.0
    avg_time_seconds: float


def _stat_value(stats: dict[str, Any], key: str) -> float:
    """Extrait ``stats[key].value`` en tolérant les deux formats Umami.

    Umami v2 renvoie ``{"pageviews": {"value": N, "prev": M}}`` mais
    certaines versions/réponses agrégées renvoient directement ``{key: N}``.
    On gère les deux pour ne pas casser sur une montée de version mineure.
    """
    raw = stats.get(key)
    if isinstance(raw, dict):
        raw = raw.get("value")
    try:
        val = float(raw) if raw is not None else 0.0
    except (ValueError, TypeError):
        return 0.0
    # Garde anti-NaN/inf : float("nan")/float("inf") sont « valides » mais
    # pollueraient bounce_rate/avg_time. On les neutralise en 0.
    return val if math.isfinite(val) else 0.0


@dataclass
class UmamiClient:
    """Wrapper minimal de l'API Umami self-host (login + lecture stats).

    Lecture seule : on ne fait aucune écriture côté Umami. Instancier via
    :meth:`from_settings` pour brancher la config runtime.
    """

    base_url: str | None
    username: str | None
    password: SecretStr | None
    website_id: str | None
    conversion_event: str | None = None

    @classmethod
    def from_settings(cls, settings: Settings) -> UmamiClient:
        return cls(
            base_url=settings.umami_base_url,
            username=settings.umami_username,
            password=settings.umami_password,
            website_id=settings.umami_website_id,
            conversion_event=settings.umami_conversion_event,
        )

    @property
    def is_configured(self) -> bool:
        return (
            bool(self.base_url)
            and bool(self.username)
            and self.password is not None
            and bool(self.website_id)
        )

    def _base(self) -> str:
        return (self.base_url or "").rstrip("/")

    async def _login(self, client: httpx.AsyncClient) -> str | None:
        """Authentifie et retourne le JWT, ou ``None`` en cas d'échec."""
        password = self.password.get_secret_value() if self.password else ""
        try:
            response = await client.post(
                f"{self._base()}/api/auth/login",
                json={"username": self.username, "password": password},
            )
        except httpx.HTTPError as exc:
            logger.error(f"Umami login échec réseau : {exc}")
            return None
        if response.status_code >= 300:
            logger.error(f"Umami login {response.status_code} : {response.text[:200]}")
            return None
        try:
            payload = response.json()
        except ValueError:
            # Corps 200 non-JSON (page d'erreur HTML d'un proxy, etc.) : on
            # respecte le contrat « aucune exception ne remonte » du module.
            logger.error("Umami login : corps de réponse non-JSON")
            return None
        token = payload.get("token") if isinstance(payload, dict) else None
        if not isinstance(token, str) or not token:
            logger.error("Umami login : token manquant dans la réponse")
            return None
        return token

    async def _get_json(
        self,
        client: httpx.AsyncClient,
        token: str,
        path: str,
        params: dict[str, Any],
    ) -> Any | None:
        """GET authentifié JSON. ``None`` si réseau KO ou statut ≥ 300."""
        try:
            response = await client.get(
                f"{self._base()}{path}",
                params=params,
                headers={"Authorization": f"Bearer {token}"},
            )
        except httpx.HTTPError as exc:
            logger.error(f"Umami GET {path} échec réseau : {exc}")
            return None
        if response.status_code >= 300:
            logger.error(f"Umami GET {path} {response.status_code} : {response.text[:200]}")
            return None
        try:
            return response.json()
        except ValueError:
            logger.error(f"Umami GET {path} : corps de réponse non-JSON")
            return None

    async def _fetch_top_paths(
        self, client: httpx.AsyncClient, token: str, start_ms: int, end_ms: int, limit: int
    ) -> list[str]:
        # Umami v3 : le breakdown des pages est ``type=path`` (la v2 utilisait
        # ``type=url``, qui renvoie 400 en v3).
        data = await self._get_json(
            client,
            token,
            f"/api/websites/{self.website_id}/metrics",
            {"type": "path", "startAt": start_ms, "endAt": end_ms},
        )
        if not isinstance(data, list):
            return []
        paths = [str(row["x"]) for row in data if isinstance(row, dict) and row.get("x")]
        return paths[:limit]

    async def _fetch_conversions(
        self, client: httpx.AsyncClient, token: str, page: str, start_ms: int, end_ms: int
    ) -> int:
        """Compte l'event ``conversion_event`` sur ``page``. 0 si non configuré."""
        if not self.conversion_event:
            return 0
        data = await self._get_json(
            client,
            token,
            f"/api/websites/{self.website_id}/metrics",
            {"type": "event", "startAt": start_ms, "endAt": end_ms, "path": page},
        )
        if not isinstance(data, list):
            return 0
        for row in data:
            if isinstance(row, dict) and str(row.get("x")) == self.conversion_event:
                try:
                    return int(row.get("y") or 0)
                except (ValueError, TypeError):
                    return 0
        return 0

    async def _fetch_page_metric(
        self, client: httpx.AsyncClient, token: str, page: str, start_ms: int, end_ms: int
    ) -> UmamiPageMetric | None:
        stats = await self._get_json(
            client,
            token,
            f"/api/websites/{self.website_id}/stats",
            {"startAt": start_ms, "endAt": end_ms, "path": page},
        )
        if not isinstance(stats, dict):
            return None
        pageviews = _stat_value(stats, "pageviews")
        visits = _stat_value(stats, "visits")
        bounces = _stat_value(stats, "bounces")
        totaltime = _stat_value(stats, "totaltime")
        # Bounce rate = sessions mono-page / sessions. avg_time = temps cumulé
        # / sessions (proxy du temps moyen par visite ; division par visits et
        # non pageviews pour rester comparable au seuil « time on page » du bot).
        visits_int = int(visits)
        bounce_rate = (bounces / visits) if visits > 0 else 0.0
        avg_time = (totaltime / visits) if visits > 0 else 0.0
        conversions = await self._fetch_conversions(client, token, page, start_ms, end_ms)
        return UmamiPageMetric(
            page=page,
            # ``visits`` sert de dénominateur CR + de garde-fou volume côté
            # bot ; on expose les sessions, pas les pageviews bruts.
            visits=visits_int if visits_int > 0 else int(pageviews),
            conversions=conversions,
            bounce_rate=round(bounce_rate, 4),
            avg_time_seconds=round(avg_time, 1),
        )

    async def fetch_landing_metrics(
        self, *, days: int = DEFAULT_WINDOW_DAYS, limit: int = DEFAULT_TOP_URLS
    ) -> list[UmamiPageMetric]:
        """Pull les métriques par page sur la fenêtre ``days``.

        Retourne ``[]`` (sans réseau) en shadow mode, et ``[]`` sur toute
        erreur d'auth/réseau — l'appelant (LandingOptimizer) gère le fallback.
        """
        if not self.is_configured:
            logger.info("Umami shadow — config incomplète, 0 métrique (fallback YAML)")
            return []

        now = datetime.now(UTC)
        end_ms = int(now.timestamp() * 1000)
        start_ms = int((now - timedelta(days=days)).timestamp() * 1000)

        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            token = await self._login(client)
            if token is None:
                return []
            pages = await self._fetch_top_paths(client, token, start_ms, end_ms, limit)
            metrics: list[UmamiPageMetric] = []
            for page in pages:
                metric = await self._fetch_page_metric(client, token, page, start_ms, end_ms)
                if metric is not None:
                    metrics.append(metric)
        logger.info(f"Umami — {len(metrics)} page(s) sur {days} j")
        return metrics


__all__ = [
    "DEFAULT_TOP_URLS",
    "DEFAULT_WINDOW_DAYS",
    "UmamiClient",
    "UmamiPageMetric",
]
