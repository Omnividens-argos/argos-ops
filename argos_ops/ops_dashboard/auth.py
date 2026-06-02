"""Durcissement auth applicatif de l'Admin Control Panel (P16.B/D).

Defense-in-depth **en complément de Caddy**, qui reste la première ligne
(TLS, basic auth, filtrage IP sur la vraie IP client). Cette couche protège
le panel si l'app est jamais exposée sans Caddy (mauvaise conf) et ajoute
une 2FA TOTP optionnelle.

Principe directeur : **fail-open quand non configuré**. En local (aucune
variable ``OPS_DASHBOARD_*``), le panel reste ouvert comme avant — la
protection ne s'arme qu'en présence d'identifiants. Ça préserve le dev et
les tests existants ; en prod le fondateur renseigne les variables.

Quatre briques (cf. :func:`request_is_authenticated`) :

- **IP allowlist** (``OPS_DASHBOARD_IP_ALLOWLIST``) — liste CIDR/IP séparée
  par virgules, évaluée sur le **peer TCP direct** (``request.client.host``).
  Vide → pas de filtrage. ⚠️ Derrière Caddy le peer est le conteneur Caddy,
  pas le visiteur : le filtrage IP « vraie IP » se fait côté Caddy (snippet
  ``infra/caddy/ops.Caddyfile``). Ici c'est un garde-fou anti-exposition
  directe.
- **Basic auth** (``OPS_DASHBOARD_BASIC_AUTH_USER`` / ``_PASSWORD``) —
  comparaison constant-time.
- **TOTP 2FA** (``OPS_DASHBOARD_TOTP_SECRET``, pyotp) — quand configuré, le
  Basic seul ne suffit plus : il faut un JWT obtenu via ``/api/auth/login``
  (basic **+** code TOTP). Sans ça, la 2FA serait contournable.
- **Session JWT HS256** (``OPS_DASHBOARD_JWT_SECRET``, PyJWT) — émis au login,
  présenté ensuite via ``Authorization: Bearer <jwt>``.
"""

from __future__ import annotations

import base64
import binascii
import ipaddress
import secrets
from datetime import UTC, datetime, timedelta

import jwt
import pyotp
from loguru import logger

from argos_ops.config import Settings

# Chemins JAMAIS protégés : healthcheck (Caddy/monitoring doivent y accéder
# sans creds), webhook Stripe (auth = signature HMAC côté handler), et
# l'endpoint de login lui-même (sinon impossible de s'authentifier).
EXEMPT_PREFIXES: tuple[str, ...] = (
    "/api/health",
    "/api/stripe/webhook",
    "/api/auth/login",
)

_JWT_ALG = "HS256"
DEFAULT_SESSION_TTL_MINUTES = 720  # 12 h — session « journée de travail »


# =============================================================================
# Activation
# =============================================================================
def is_basic_auth_enabled(settings: Settings) -> bool:
    """L'auth applicative est armée dès que user + password sont définis."""
    return bool(settings.ops_dashboard_basic_auth_user) and (
        settings.ops_dashboard_basic_auth_password is not None
    )


def is_path_exempt(path: str) -> bool:
    # Match sur frontière de segment : ``/api/health`` exempte ``/api/health``
    # et ``/api/health/x`` mais PAS ``/api/healthz`` (sinon un préfixe nu
    # ouvrirait des routes voisines à l'insu de l'auth).
    return any(path == prefix or path.startswith(prefix + "/") for prefix in EXEMPT_PREFIXES)


# =============================================================================
# Basic auth
# =============================================================================
def parse_basic_credentials(header: str | None) -> tuple[str, str] | None:
    """Décode un header ``Authorization: Basic base64(user:pass)``.

    Retourne ``None`` si absent/malformé (jamais d'exception).
    """
    if not header or not header.startswith("Basic "):
        return None
    encoded = header[len("Basic ") :].strip()
    try:
        decoded = base64.b64decode(encoded, validate=True).decode("utf-8")
    except (binascii.Error, ValueError):
        return None
    if ":" not in decoded:
        return None
    user, _, password = decoded.partition(":")
    return user, password


def verify_basic_auth(user: str, password: str, settings: Settings) -> bool:
    """Compare les identifiants en constant-time (anti timing-oracle).

    On compare les deux champs même si le user diffère, pour ne pas révéler
    via le timing lequel est faux.
    """
    expected_user = settings.ops_dashboard_basic_auth_user or ""
    expected_pw = (
        settings.ops_dashboard_basic_auth_password.get_secret_value()
        if settings.ops_dashboard_basic_auth_password is not None
        else ""
    )
    user_ok = secrets.compare_digest(user.encode("utf-8"), expected_user.encode("utf-8"))
    pw_ok = secrets.compare_digest(password.encode("utf-8"), expected_pw.encode("utf-8"))
    return user_ok and pw_ok


# =============================================================================
# IP allowlist
# =============================================================================
def _parse_networks(raw: str | None) -> list[ipaddress.IPv4Network | ipaddress.IPv6Network]:
    nets: list[ipaddress.IPv4Network | ipaddress.IPv6Network] = []
    for token in (raw or "").split(","):
        token = token.strip()
        if not token:
            continue
        try:
            nets.append(ipaddress.ip_network(token, strict=False))
        except ValueError:
            logger.warning(f"OPS allowlist : entrée IP invalide ignorée : {token!r}")
    return nets


def ip_is_allowed(client_ip: str | None, settings: Settings) -> bool:
    """Vrai si ``client_ip`` est dans l'allowlist (ou si l'allowlist est vide)."""
    nets = _parse_networks(settings.ops_dashboard_ip_allowlist)
    if not nets:
        return True  # pas de filtrage (cf. .env.example : vide = ouvert)
    if not client_ip:
        return False  # allowlist active mais peer inconnu → refus prudent
    try:
        addr = ipaddress.ip_address(client_ip)
    except ValueError:
        return False
    return any(addr in net for net in nets)


# =============================================================================
# TOTP
# =============================================================================
def is_totp_enabled(settings: Settings) -> bool:
    return settings.ops_dashboard_totp_secret is not None


def verify_totp(code: str, settings: Settings) -> bool:
    """Vérifie un code TOTP. ``True`` si TOTP non configuré (rien à vérifier).

    ``valid_window=1`` tolère le drift d'horloge (±1 pas de 30 s).
    """
    secret = settings.ops_dashboard_totp_secret
    if secret is None:
        return True
    if not code:
        return False
    totp = pyotp.TOTP(secret.get_secret_value())
    return bool(totp.verify(code, valid_window=1))


# =============================================================================
# Session JWT
# =============================================================================
def issue_session_token(
    subject: str,
    settings: Settings,
    *,
    now: datetime | None = None,
    ttl_minutes: int = DEFAULT_SESSION_TTL_MINUTES,
) -> str:
    """Émet un JWT HS256 ``{sub, iat, exp}``. Lève si ``JWT_SECRET`` absent."""
    secret = settings.ops_dashboard_jwt_secret
    if secret is None:
        raise ValueError("OPS_DASHBOARD_JWT_SECRET non configuré")
    now = now or datetime.now(UTC)
    payload = {
        "sub": subject,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=ttl_minutes)).timestamp()),
    }
    return jwt.encode(payload, secret.get_secret_value(), algorithm=_JWT_ALG)


def verify_session_token(token: str, settings: Settings) -> str | None:
    """Valide un JWT et retourne le ``sub``, ou ``None`` si invalide/expiré.

    Algorithme **figé** à HS256 (``algorithms=[_JWT_ALG]``) : PyJWT rejette
    ``alg: none`` et toute confusion d'algorithme.
    """
    secret = settings.ops_dashboard_jwt_secret
    if secret is None:
        return None
    try:
        payload = jwt.decode(token, secret.get_secret_value(), algorithms=[_JWT_ALG])
    except jwt.PyJWTError:
        return None
    sub = payload.get("sub")
    return sub if isinstance(sub, str) else None


# =============================================================================
# Décision d'auth d'une requête
# =============================================================================
def request_is_authenticated(authorization: str | None, settings: Settings) -> bool:
    """Une requête est authentifiée si JWT valide, ou Basic valide (si pas de TOTP).

    Quand TOTP est configuré, le Basic seul est REFUSÉ : la seule voie est le
    JWT émis par ``/api/auth/login`` (qui exige le code TOTP). Sinon la 2FA
    serait triviale à contourner en envoyant juste le header Basic.
    """
    if (
        authorization
        and authorization.startswith("Bearer ")
        and settings.ops_dashboard_jwt_secret is not None
        and verify_session_token(authorization[len("Bearer ") :].strip(), settings) is not None
    ):
        return True
    if not is_totp_enabled(settings):
        creds = parse_basic_credentials(authorization)
        if creds is not None and verify_basic_auth(creds[0], creds[1], settings):
            return True
    return False


__all__ = [
    "DEFAULT_SESSION_TTL_MINUTES",
    "EXEMPT_PREFIXES",
    "ip_is_allowed",
    "is_basic_auth_enabled",
    "is_path_exempt",
    "is_totp_enabled",
    "issue_session_token",
    "parse_basic_credentials",
    "request_is_authenticated",
    "verify_basic_auth",
    "verify_session_token",
    "verify_totp",
]
