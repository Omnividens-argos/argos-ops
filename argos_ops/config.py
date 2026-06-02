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
    discord_webhook_inbox: SecretStr | None = Field(default=None, alias="DISCORD_WEBHOOK_INBOX")
    discord_founder_user_id: str | None = Field(default=None, alias="DISCORD_FOUNDER_USER_ID")

    # --- Email OVH Zimbra (P5 EmailBot, D-018) ---
    email_imap_host: str = Field(default="ssl0.ovh.net", alias="EMAIL_IMAP_HOST")
    email_imap_port: int = Field(default=993, alias="EMAIL_IMAP_PORT")
    email_smtp_host: str = Field(default="ssl0.ovh.net", alias="EMAIL_SMTP_HOST")
    email_smtp_port: int = Field(default=465, alias="EMAIL_SMTP_PORT")
    email_user: str | None = Field(default=None, alias="EMAIL_USER")
    email_password: SecretStr | None = Field(default=None, alias="EMAIL_PASSWORD")
    email_reply_name: str = Field(default="Argos par Omnividens", alias="EMAIL_REPLY_NAME")

    # --- Signature email (cohérente sur tous les envois Argos Ops) ---
    # Ces 3 variables ont des defaults raisonnables, override via .env si besoin.
    email_signature_tagline: str = Field(
        default="Argos — on scanne, vous corrigez.",
        alias="EMAIL_SIGNATURE_TAGLINE",
    )
    email_signature_site_url: str = Field(
        default="https://omnividens.fr",
        alias="EMAIL_SIGNATURE_SITE_URL",
    )
    # Wording AI Act art. 50 (transparence IA) — court, factuel
    email_signature_ai_disclosure: str = Field(
        default="Email rédigé par notre assistant Argos Ops.",
        alias="EMAIL_SIGNATURE_AI_DISCLOSURE",
    )

    # --- Stripe (P7 FinanceBot — compte partagé avec SecHunter, P0 décision) ---
    stripe_secret_key: SecretStr | None = Field(default=None, alias="STRIPE_SECRET_KEY")
    stripe_webhook_secret: SecretStr | None = Field(default=None, alias="STRIPE_WEBHOOK_SECRET")
    # Garde-fou : tant que le wording des relances n'a pas été validé en
    # condition réelle, on désactive l'envoi outbound. Le bot fait tout le
    # reste (sync companies, calcul MRR, notif Discord). À passer à 'true'
    # une fois le premier run live audité.
    financebot_dunning_enabled: bool = Field(default=False, alias="FINANCEBOT_DUNNING_ENABLED")

    # --- Outbound (P13 — shadow mode par défaut) ---
    # Live mode = envoi réel via Zimbra SMTP depuis le domaine secondaire.
    # Reste sur False tant que le domaine secondaire n'est pas acquis et
    # warmed-up 4 semaines (cf. P13 § 13.2). Indépendant de FINANCEBOT_DUNNING_ENABLED.
    outbound_live_mode: bool = Field(default=False, alias="OUTBOUND_LIVE_MODE")
    # Domaine sacrificiel pour préserver la réputation `omnividens.fr` (P13 § 13.2).
    # Ex : "try-omnividens.com", "hello-omnividens.com". Vide tant que pas acheté.
    outbound_from_domain: str | None = Field(default=None, alias="OUTBOUND_FROM_DOMAIN")
    # Secret HMAC pour signer les liens d'opt-out (1-clic, P17 conformité).
    # Rotation = revocation globale de tous les liens d'opt-out existants.
    outbound_unsubscribe_secret: SecretStr | None = Field(
        default=None, alias="OUTBOUND_UNSUBSCRIBE_SECRET"
    )
    # Cap journalier d'envois — protection délivrabilité (warmup et croisière).
    # Breaker `outbound_volume_exceeded` se déclenche si dépassement détecté.
    outbound_daily_max: int = Field(default=30, alias="OUTBOUND_DAILY_MAX")

    # --- Social P11 (D-024 LinkedIn / D-025 Mastodon) ---
    # LinkedIn App #1 — profil perso (Share on LinkedIn, scope w_member_social).
    linkedin_personal_access_token: SecretStr | None = Field(
        default=None, alias="LINKEDIN_PERSONAL_ACCESS_TOKEN"
    )
    linkedin_personal_urn: str | None = Field(default=None, alias="LINKEDIN_PERSONAL_URN")
    # LinkedIn App #2 — Page Omnividens (Community Management API).
    # Bloqué tant que LinkedIn n'a pas approuvé CMA (cf. memo project).
    linkedin_page_access_token: SecretStr | None = Field(
        default=None, alias="LINKEDIN_PAGE_ACCESS_TOKEN"
    )
    linkedin_page_urn: str | None = Field(default=None, alias="LINKEDIN_PAGE_URN")
    # Legacy aliases conservés en lecture (.env anciens). Préférer Personal/Page.
    linkedin_api_token: SecretStr | None = Field(default=None, alias="LINKEDIN_API_TOKEN")
    linkedin_org_urn: str | None = Field(default=None, alias="LINKEDIN_ORG_URN")
    mastodon_instance_url: str = Field(
        default="https://infosec.exchange", alias="MASTODON_INSTANCE_URL"
    )
    mastodon_access_token: SecretStr | None = Field(default=None, alias="MASTODON_ACCESS_TOKEN")
    # Bluesky (Sprint B — AT Protocol, gratuit illimité). Auth = handle +
    # app password (Settings → App Passwords), jamais le mot de passe du
    # compte. Shadow tant que l'un des deux manque. ``pds_url`` = serveur PDS
    # (par défaut bsky.social ; override si self-host AT Protocol un jour).
    bluesky_handle: str | None = Field(default=None, alias="BLUESKY_HANDLE")
    bluesky_app_password: SecretStr | None = Field(default=None, alias="BLUESKY_APP_PASSWORD")
    bluesky_pds_url: str = Field(default="https://bsky.social", alias="BLUESKY_PDS_URL")
    # Meta / Facebook Page (organique — Sprint contenu, persona TPE/PME).
    # DISTINCT du connecteur Ads (META_ADS_*). Token de Page long-lived,
    # scope pages_manage_posts (token de Page via Meta Business Suite). Shadow tant
    # que page_id OU token manque. ``graph_api_version`` overridable.
    meta_page_id: str | None = Field(default=None, alias="META_PAGE_ID")
    meta_page_access_token: SecretStr | None = Field(default=None, alias="META_PAGE_ACCESS_TOKEN")
    meta_graph_api_version: str = Field(default="v21.0", alias="META_GRAPH_API_VERSION")
    # X / Twitter (Sprint contenu — draft-only). Token user-context OAuth 2.0
    # (scope tweet.write), PAS l'app-only bearer. Shadow tant qu'absent.
    # Activation live reportée : le fondateur arbitrera Free vs Basic ($).
    x_access_token: SecretStr | None = Field(default=None, alias="X_ACCESS_TOKEN")
    x_api_base: str = Field(default="https://api.twitter.com", alias="X_API_BASE")
    # Truth Social (Sprint contenu — fork Mastodon, draft-only). Même API que
    # Mastodon (POST /api/v1/statuses + Bearer). Accès API à demander par le
    # fondateur ; shadow tant que le token manque. Canal le plus expérimental
    # (fit audience ~nul vs ICP Argos — cf. skill truth-social-writer).
    truth_social_instance_url: str = Field(
        default="https://truthsocial.com", alias="TRUTH_SOCIAL_INSTANCE_URL"
    )
    truth_social_access_token: SecretStr | None = Field(
        default=None, alias="TRUTH_SOCIAL_ACCESS_TOKEN"
    )
    content_daily_max_per_channel: int = Field(default=3, alias="CONTENT_DAILY_MAX_PER_CHANNEL")
    discord_webhook_content: SecretStr | None = Field(default=None, alias="DISCORD_WEBHOOK_CONTENT")

    # --- AdBot live (D-026 budget pub) ---
    ads_live_mode: bool = Field(default=False, alias="ADS_LIVE_MODE")
    ads_daily_budget_eur: int = Field(default=0, alias="ADS_DAILY_BUDGET_EUR")
    google_ads_developer_token: SecretStr | None = Field(
        default=None, alias="GOOGLE_ADS_DEVELOPER_TOKEN"
    )
    linkedin_ads_account_id: str | None = Field(default=None, alias="LINKEDIN_ADS_ACCOUNT_ID")
    meta_ads_access_token: SecretStr | None = Field(default=None, alias="META_ADS_ACCESS_TOKEN")

    # --- Analytics Umami (INFRA-02 — self-host analytics.omnividens.fr) ---
    # Source des métriques landing pour LandingOptimizer. Umami est un
    # analytics open-source self-hosté (Docker, gratuit, sans cookie) : 100 %
    # local, conforme D-017 (aucune API SaaS tierce). Tant qu'une des 4 vars
    # manque, le client est en shadow et LandingOptimizer retombe sur le YAML
    # manuel data/analytics/landing_perf.yaml.
    umami_base_url: str | None = Field(default=None, alias="UMAMI_BASE_URL")
    umami_username: str | None = Field(default=None, alias="UMAMI_USERNAME")
    umami_password: SecretStr | None = Field(default=None, alias="UMAMI_PASSWORD")
    umami_website_id: str | None = Field(default=None, alias="UMAMI_WEBSITE_ID")
    # Nom de l'event Umami compté comme conversion (ex : "demande-demo").
    # Vide → conversions=0 (la proposition « CR < 1 % » ne se déclenche pas).
    umami_conversion_event: str | None = Field(default=None, alias="UMAMI_CONVERSION_EVENT")

    # --- Admin Control Panel auth (P16.B/D — durcissement applicatif) ---
    # Defense-in-depth en complément de Caddy. Tout est fail-open si non
    # renseigné : le panel reste ouvert en local (et les tests passent). En
    # prod le fondateur renseigne ces vars. Cf. docs/INFRA_OPS_PANEL.md.
    ops_dashboard_basic_auth_user: str | None = Field(
        default=None, alias="OPS_DASHBOARD_BASIC_AUTH_USER"
    )
    ops_dashboard_basic_auth_password: SecretStr | None = Field(
        default=None, alias="OPS_DASHBOARD_BASIC_AUTH_PASSWORD"
    )
    # Secret de signature des JWT de session (HS256). openssl rand -hex 32.
    ops_dashboard_jwt_secret: SecretStr | None = Field(
        default=None, alias="OPS_DASHBOARD_JWT_SECRET"
    )
    # Allowlist IP/CIDR séparée par virgules, évaluée sur le peer TCP direct.
    # Vide = pas de filtrage applicatif (le vrai filtrage IP est côté Caddy).
    ops_dashboard_ip_allowlist: str | None = Field(default=None, alias="OPS_DASHBOARD_IP_ALLOWLIST")
    # Secret TOTP (base32) pour la 2FA. Quand présent, le Basic seul ne suffit
    # plus : login via /api/auth/login (basic + code) → JWT.
    ops_dashboard_totp_secret: SecretStr | None = Field(
        default=None, alias="OPS_DASHBOARD_TOTP_SECRET"
    )

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
