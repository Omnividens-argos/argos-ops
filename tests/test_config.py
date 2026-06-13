"""Tests du module config (pydantic-settings)."""

from __future__ import annotations

import pytest

from argos_ops import config
from argos_ops.config import Settings


def test_refresh_settings_returns_fresh_instance() -> None:
    """``refresh_settings`` relit .env/.env.local à chaud (Axe 4) : chaque appel
    crée une nouvelle instance et la promeut en singleton."""
    a = config.refresh_settings()
    b = config.refresh_settings()
    assert isinstance(a, Settings)
    assert a is not b  # relecture → nouvelle instance à chaque appel
    assert config.get_settings() is b  # le singleton = dernière relecture


def test_settings_async_url_rewrites_postgresql() -> None:
    s = Settings(DATABASE_URL="postgresql://u:p@h:5432/db")  # type: ignore[call-arg]
    assert s.async_database_url == "postgresql+psycopg://u:p@h:5432/db"


def test_settings_async_url_passthrough_if_already_async() -> None:
    s = Settings(DATABASE_URL="postgresql+psycopg://u:p@h/db")  # type: ignore[call-arg]
    assert s.async_database_url == "postgresql+psycopg://u:p@h/db"


def test_settings_secret_str_does_not_leak_in_repr() -> None:
    s = Settings(GEMINI_API_KEY="sk-secret-do-not-leak")  # type: ignore[call-arg]
    assert "sk-secret-do-not-leak" not in repr(s)
    assert s.gemini_api_key is not None
    assert s.gemini_api_key.get_secret_value() == "sk-secret-do-not-leak"


def test_settings_log_level_validates_literal() -> None:
    with pytest.raises(ValueError):
        Settings(ARGOS_OPS_LOG_LEVEL="VERBOSE")  # type: ignore[arg-type, call-arg]
