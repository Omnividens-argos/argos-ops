"""Tests du durcissement auth du panel (P16.B/D).

Deux niveaux :

- **unitaire** sur :mod:`argos_ops.ops_dashboard.auth` (briques pures :
  parsing Basic, constant-time, allowlist CIDR, TOTP, JWT, décision d'auth).
- **intégration** via ``TestClient`` : on patche ``get_settings`` dans le
  module app pour armer l'auth et vérifier le middleware (401/403, exemptions,
  login → JWT, JWT accepté de bout en bout).

Le fail-open (aucune var configurée → panel ouvert) est déjà couvert par les
28 tests existants de ``test_ops_dashboard`` ; on ajoute ici une assertion
explicite.
"""

from __future__ import annotations

import base64
from contextlib import asynccontextmanager
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pyotp
import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from argos_ops.config import Settings
from argos_ops.ops_dashboard import app as app_module
from argos_ops.ops_dashboard import auth
from argos_ops.ops_dashboard.app import app


def _settings(**over: Any) -> Settings:
    """Settings minimal (model_construct = pas de chargement .env) pour l'auth."""
    base: dict[str, Any] = {
        "ops_dashboard_basic_auth_user": None,
        "ops_dashboard_basic_auth_password": None,
        "ops_dashboard_jwt_secret": None,
        "ops_dashboard_ip_allowlist": None,
        "ops_dashboard_totp_secret": None,
    }
    base.update(over)
    return Settings.model_construct(**base)


def _basic_header(user: str, password: str) -> dict[str, str]:
    raw = base64.b64encode(f"{user}:{password}".encode()).decode()
    return {"Authorization": f"Basic {raw}"}


# Secrets de test ≥ 32 octets : minimum HMAC-SHA256 (RFC 7518), évite les
# InsecureKeyLengthWarning de PyJWT.
_JWT_KEY = "0123456789abcdef0123456789abcdef"
_JWT_KEY_B = "fedcba9876543210fedcba9876543210"


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


# =============================================================================
# parse_basic_credentials
# =============================================================================
def test_parse_basic_credentials_ok() -> None:
    header = _basic_header("admin", "p@ss:word")["Authorization"]  # ':' dans le pw
    assert auth.parse_basic_credentials(header) == ("admin", "p@ss:word")


@pytest.mark.parametrize(
    "header",
    [
        None,
        "",
        "Bearer xyz",
        "Basic !!notbase64!!",
        "Basic " + base64.b64encode(b"nocolon").decode(),
    ],
)
def test_parse_basic_credentials_rejects_malformed(header: str | None) -> None:
    assert auth.parse_basic_credentials(header) is None


# =============================================================================
# verify_basic_auth / is_basic_auth_enabled
# =============================================================================
def test_verify_basic_auth_constant_time_match() -> None:
    s = _settings(
        ops_dashboard_basic_auth_user="admin",
        ops_dashboard_basic_auth_password=SecretStr("s3cret"),
    )
    assert auth.verify_basic_auth("admin", "s3cret", s) is True
    assert auth.verify_basic_auth("admin", "wrong", s) is False
    assert auth.verify_basic_auth("root", "s3cret", s) is False


def test_is_basic_auth_enabled_requires_both() -> None:
    assert auth.is_basic_auth_enabled(_settings()) is False
    assert auth.is_basic_auth_enabled(_settings(ops_dashboard_basic_auth_user="admin")) is False
    assert (
        auth.is_basic_auth_enabled(
            _settings(
                ops_dashboard_basic_auth_user="admin",
                ops_dashboard_basic_auth_password=SecretStr("p"),
            )
        )
        is True
    )


# =============================================================================
# ip_is_allowed
# =============================================================================
def test_ip_allowlist_empty_allows_all() -> None:
    assert auth.ip_is_allowed("203.0.113.7", _settings()) is True
    assert auth.ip_is_allowed(None, _settings()) is True


def test_ip_allowlist_cidr_and_single() -> None:
    s = _settings(ops_dashboard_ip_allowlist="10.0.0.0/8, 203.0.113.7")
    assert auth.ip_is_allowed("10.4.2.1", s) is True  # dans le /8
    assert auth.ip_is_allowed("203.0.113.7", s) is True  # IP exacte
    assert auth.ip_is_allowed("198.51.100.2", s) is False  # hors liste


def test_ip_allowlist_rejects_unknown_or_invalid_peer() -> None:
    s = _settings(ops_dashboard_ip_allowlist="10.0.0.0/8")
    assert auth.ip_is_allowed(None, s) is False  # allowlist active mais peer inconnu
    assert auth.ip_is_allowed("not-an-ip", s) is False


def test_ip_allowlist_ignores_invalid_entries() -> None:
    # Une entrée pourrie ne doit pas faire planter ni tout ouvrir.
    s = _settings(ops_dashboard_ip_allowlist="garbage, 10.0.0.0/8")
    assert auth.ip_is_allowed("10.1.1.1", s) is True
    assert auth.ip_is_allowed("8.8.8.8", s) is False


def test_ip_allowlist_ipv6() -> None:
    s = _settings(ops_dashboard_ip_allowlist="2001:db8::/32")
    assert auth.ip_is_allowed("2001:db8::1", s) is True
    assert auth.ip_is_allowed("2001:dead::1", s) is False


# =============================================================================
# TOTP
# =============================================================================
def test_verify_totp_skipped_when_not_configured() -> None:
    assert auth.verify_totp("", _settings()) is True
    assert auth.is_totp_enabled(_settings()) is False


def test_verify_totp_valid_and_invalid() -> None:
    secret = pyotp.random_base32()
    s = _settings(ops_dashboard_totp_secret=SecretStr(secret))
    assert auth.is_totp_enabled(s) is True
    valid = pyotp.TOTP(secret).now()
    assert auth.verify_totp(valid, s) is True
    assert auth.verify_totp("000000", s) is False
    assert auth.verify_totp("", s) is False  # code vide refusé quand TOTP armé


# =============================================================================
# JWT
# =============================================================================
def test_jwt_roundtrip() -> None:
    s = _settings(ops_dashboard_jwt_secret=SecretStr(_JWT_KEY))
    token = auth.issue_session_token("admin", s)
    assert auth.verify_session_token(token, s) == "admin"


def test_jwt_rejects_wrong_secret_and_tampering() -> None:
    s1 = _settings(ops_dashboard_jwt_secret=SecretStr(_JWT_KEY))
    s2 = _settings(ops_dashboard_jwt_secret=SecretStr(_JWT_KEY_B))
    token = auth.issue_session_token("admin", s1)
    assert auth.verify_session_token(token, s2) is None  # mauvaise clé
    assert auth.verify_session_token(token + "x", s1) is None  # altéré
    assert auth.verify_session_token("not.a.jwt", s1) is None


def test_jwt_rejects_expired() -> None:
    from datetime import UTC, datetime, timedelta

    s = _settings(ops_dashboard_jwt_secret=SecretStr(_JWT_KEY))
    past = datetime.now(UTC) - timedelta(hours=2)
    token = auth.issue_session_token("admin", s, now=past, ttl_minutes=1)
    assert auth.verify_session_token(token, s) is None


def test_issue_token_requires_secret() -> None:
    with pytest.raises(ValueError, match="JWT_SECRET"):
        auth.issue_session_token("admin", _settings())
    assert auth.verify_session_token("whatever", _settings()) is None


# =============================================================================
# request_is_authenticated — combinaison Basic / JWT / TOTP
# =============================================================================
def test_request_auth_basic_accepted_without_totp() -> None:
    s = _settings(
        ops_dashboard_basic_auth_user="admin",
        ops_dashboard_basic_auth_password=SecretStr("pw"),
    )
    header = _basic_header("admin", "pw")["Authorization"]
    assert auth.request_is_authenticated(header, s) is True
    assert auth.request_is_authenticated(_basic_header("admin", "bad")["Authorization"], s) is False


def test_request_auth_basic_refused_when_totp_enabled() -> None:
    # 2FA armée : le Basic seul ne suffit plus, il faut un JWT.
    s = _settings(
        ops_dashboard_basic_auth_user="admin",
        ops_dashboard_basic_auth_password=SecretStr("pw"),
        ops_dashboard_jwt_secret=SecretStr(_JWT_KEY),
        ops_dashboard_totp_secret=SecretStr(pyotp.random_base32()),
    )
    assert auth.request_is_authenticated(_basic_header("admin", "pw")["Authorization"], s) is False
    token = auth.issue_session_token("admin", s)
    assert auth.request_is_authenticated(f"Bearer {token}", s) is True


def test_request_auth_bearer_jwt_accepted() -> None:
    s = _settings(
        ops_dashboard_basic_auth_user="admin",
        ops_dashboard_basic_auth_password=SecretStr("pw"),
        ops_dashboard_jwt_secret=SecretStr(_JWT_KEY),
    )
    token = auth.issue_session_token("admin", s)
    assert auth.request_is_authenticated(f"Bearer {token}", s) is True
    assert auth.request_is_authenticated("Bearer garbage", s) is False


# =============================================================================
# is_path_exempt
# =============================================================================
def test_path_exemptions() -> None:
    assert auth.is_path_exempt("/api/health") is True
    assert auth.is_path_exempt("/api/stripe/webhook") is True
    assert auth.is_path_exempt("/api/auth/login") is True
    assert auth.is_path_exempt("/api/agents") is False
    # Pas de bypass par extension de préfixe (frontière de segment).
    assert auth.is_path_exempt("/api/healthz") is False
    assert auth.is_path_exempt("/api/stripe/webhook-evil") is False


# =============================================================================
# Intégration middleware (TestClient)
# =============================================================================
_AUTH_CFG = {
    "ops_dashboard_basic_auth_user": "admin",
    "ops_dashboard_basic_auth_password": SecretStr("s3cret"),
    "ops_dashboard_jwt_secret": SecretStr(_JWT_KEY),
}


def test_fail_open_when_unconfigured(client: TestClient) -> None:
    # Aucune var auth → 404 (pas 401) sur un agent inconnu : le middleware
    # laisse passer jusqu'au handler.
    with patch.object(app_module, "get_settings", lambda: _settings()):
        resp = client.get("/api/agents/UnknownBot/runs")
    assert resp.status_code == 404


def test_protected_route_401_without_credentials(client: TestClient) -> None:
    with patch.object(app_module, "get_settings", lambda: _settings(**_AUTH_CFG)):
        resp = client.get("/api/agents")
    assert resp.status_code == 401
    assert resp.headers.get("WWW-Authenticate") == 'Basic realm="Argos Ops"'


def test_protected_route_passes_with_valid_basic(client: TestClient) -> None:
    cfg = _settings(**_AUTH_CFG)
    with (
        patch.object(app_module, "get_settings", lambda: cfg),
        patch.object(app_module, "session_scope", _fake_scope()),
        patch.object(app_module, "get_last_run_per_agent", AsyncMock(return_value={})),
        patch.object(app_module, "list_tripped_breakers", AsyncMock(return_value=[])),
    ):
        resp = client.get("/api/agents", headers=_basic_header("admin", "s3cret"))
    assert resp.status_code == 200  # creds valides → traverse le middleware


def test_health_is_exempt_even_when_auth_armed(client: TestClient) -> None:
    fake_session = MagicMock(name="fake-session")
    fake_session.execute = AsyncMock()

    @asynccontextmanager
    async def _scope():  # type: ignore[no-untyped-def]
        yield fake_session

    with (
        patch.object(app_module, "get_settings", lambda: _settings(**_AUTH_CFG)),
        patch.object(app_module, "session_scope", _scope),
    ):
        resp = client.get("/api/health")  # pas de creds
    assert resp.status_code == 200


def test_ip_allowlist_blocks_with_403(client: TestClient) -> None:
    # TestClient a un peer "testclient" (pas une IP) → hors allowlist → 403,
    # et ça court-circuite avant même l'exemption (IP = filtre global).
    cfg = _settings(ops_dashboard_ip_allowlist="10.0.0.0/8")
    with patch.object(app_module, "get_settings", lambda: cfg):
        resp = client.get("/api/health")
    assert resp.status_code == 403


# =============================================================================
# Login endpoint
# =============================================================================
def test_login_success_returns_jwt(client: TestClient) -> None:
    cfg = _settings(**_AUTH_CFG)
    with patch.object(app_module, "get_settings", lambda: cfg):
        resp = client.post("/api/auth/login", json={"username": "admin", "password": "s3cret"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["token_type"] == "bearer"
    assert auth.verify_session_token(body["token"], cfg) == "admin"


def test_login_rejects_bad_password(client: TestClient) -> None:
    with patch.object(app_module, "get_settings", lambda: _settings(**_AUTH_CFG)):
        resp = client.post("/api/auth/login", json={"username": "admin", "password": "nope"})
    assert resp.status_code == 401


def test_login_requires_totp_when_configured(client: TestClient) -> None:
    secret = pyotp.random_base32()
    cfg = _settings(**_AUTH_CFG, ops_dashboard_totp_secret=SecretStr(secret))
    with patch.object(app_module, "get_settings", lambda: cfg):
        bad = client.post("/api/auth/login", json={"username": "admin", "password": "s3cret"})
        assert bad.status_code == 401  # code TOTP manquant
        good = client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "s3cret", "totp_code": pyotp.TOTP(secret).now()},
        )
    assert good.status_code == 200


def test_login_404_when_auth_disabled(client: TestClient) -> None:
    with patch.object(app_module, "get_settings", lambda: _settings()):
        resp = client.post("/api/auth/login", json={"username": "x", "password": "y"})
    assert resp.status_code == 404


def test_login_503_when_jwt_secret_missing(client: TestClient) -> None:
    cfg = _settings(
        ops_dashboard_basic_auth_user="admin",
        ops_dashboard_basic_auth_password=SecretStr("s3cret"),
    )  # pas de jwt_secret
    with patch.object(app_module, "get_settings", lambda: cfg):
        resp = client.post("/api/auth/login", json={"username": "admin", "password": "s3cret"})
    assert resp.status_code == 503


# Helper : faux session_scope réutilisable
def _fake_scope() -> Any:
    @asynccontextmanager
    async def _scope():  # type: ignore[no-untyped-def]
        yield MagicMock(name="fake-session")

    return _scope
