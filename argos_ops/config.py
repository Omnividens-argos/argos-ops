"""Configuration runtime Argos Ops.

Charge depuis ``.env.local`` (dev) ou ``.env`` (prod), avec fallback sur les
variables d'environnement systèmes. Pas de valeur par défaut sensible : si
une clé est manquante quand un agent en a besoin, on échoue tôt et fort.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """Variables d'environnement consommées par l'app.

    Toute variable secrète est typée ``SecretStr`` pour éviter les fuites
    accidentelles dans les logs (loguru.repr) ou les exceptions Pydantic.
    """

    model_config = SettingsConfigDict(
        env_file=(REPO_ROOT / ".env", REPO_ROOT / ".env.local"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True,
    )

    # --- Core ---
    argos_ops_log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(
        default="INFO", alias="ARGOS_OPS_LOG_LEVEL"
    )

    # --- Database / Redis ---
    database_url: str = Field(
        default="postgresql+psycopg://argos_ops:CHANGE_ME@localhost:5432/argos_ops",
        alias="DATABASE_URL",
    )
    redis_url: str = Field(default="redis://localhost:6379/3", alias="REDIS_URL")

    # --- Gemini (DÉPRÉCIÉ pour Argos Ops par D-017) ---
    # Conservé optionnel uniquement pour le scanner SecHunter BYOK (D-011),
    # produit séparé. Argos Ops lui-même n'appelle plus Gemini : embeddings
    # via fastembed local, agents via Claude Code Pro Max.
    gemini_api_key: SecretStr | None = Field(default=None, alias="GEMINI_API_KEY")

    # --- Discord (P4) ---
    discord_webhook_digest: SecretStr | None = Field(default=None, alias="DISCORD_WEBHOOK_DIGEST")
    discord_webhook_escalations: SecretStr | None = Field(
        default=None, alias="DISCORD_WEBHOOK_ESCALATIONS"
    )
    discord_webhook_alerts: SecretStr | None = Field(default=None, alias="DISCORD_WEBHOOK_ALERTS")
    discord_webhook_ops_logs: SecretStr | None = Field(
        default=None, alias="DISCORD_WEBHOOK_OPS_LOGS"
    )
    discord_founder_user_id: str | None = Field(default=None, alias="DISCORD_FOUNDER_USER_ID")

    @property
    def async_database_url(self) -> str:
        """URL adaptée à SQLAlchemy async (driver psycopg v3).

        ``postgresql://`` → ``postgresql+psycopg://`` pour forcer le driver
        async. Idempotent si l'URL inclut déjà un driver.
        """
        url = self.database_url
        if url.startswith("postgresql://"):
            return "postgresql+psycopg://" + url.removeprefix("postgresql://")
        return url


_settings: Settings | None = None


def get_settings() -> Settings:
    """Singleton — Settings est immuable par run."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


__all__ = ["REPO_ROOT", "Settings", "get_settings"]
