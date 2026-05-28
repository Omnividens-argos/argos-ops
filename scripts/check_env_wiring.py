"""Validateur d'env vars Argos Ops — diagnostique ce qui manque par bot.

Lit ``.env.local`` (sans afficher les valeurs, juste présence/longueur) et
imprime un rapport groupé par feature/bot. Code retour 0 si tous les
groupes ``required`` sont complets, 1 sinon.

Usage :
    uv run python scripts/check_env_wiring.py
    uv run python scripts/check_env_wiring.py --json
    uv run python scripts/check_env_wiring.py --only linkedin,stripe
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass, field

from dotenv import load_dotenv


@dataclass(frozen=True)
class EnvGroup:
    """Groupe logique d'env vars pour un bot ou une feature."""

    key: str
    label: str
    required: tuple[str, ...] = ()
    optional: tuple[str, ...] = ()
    note: str = ""


GROUPS: tuple[EnvGroup, ...] = (
    EnvGroup(
        key="core",
        label="Core / Database / Redis",
        required=("DATABASE_URL",),
        optional=("ARGOS_OPS_LOG_LEVEL", "REDIS_URL"),
    ),
    EnvGroup(
        key="discord",
        label="Discord webhooks (alerts, digest, escalations, ops logs)",
        required=("DISCORD_WEBHOOK_OPS_LOGS",),
        optional=(
            "DISCORD_WEBHOOK_DIGEST",
            "DISCORD_WEBHOOK_ESCALATIONS",
            "DISCORD_WEBHOOK_ALERTS",
            "DISCORD_WEBHOOK_INBOX",
            "DISCORD_WEBHOOK_CONTENT",
            "DISCORD_FOUNDER_USER_ID",
        ),
    ),
    EnvGroup(
        key="email",
        label="Email OVH Zimbra (EmailBot P5, D-018)",
        required=("EMAIL_USER", "EMAIL_PASSWORD"),
        optional=(
            "EMAIL_IMAP_HOST",
            "EMAIL_IMAP_PORT",
            "EMAIL_SMTP_HOST",
            "EMAIL_SMTP_PORT",
            "EMAIL_REPLY_NAME",
        ),
    ),
    EnvGroup(
        key="mastodon",
        label="Mastodon (ContentBot P11, D-025)",
        required=("MASTODON_INSTANCE_URL", "MASTODON_ACCESS_TOKEN"),
        note="Settings → Development → New application, scopes write:statuses + read:accounts",
    ),
    EnvGroup(
        key="linkedin_personal",
        label="LinkedIn App #1 — profil perso (ContentBot P11)",
        required=(
            "LINKEDIN_PERSONAL_CLIENT_ID",
            "LINKEDIN_PERSONAL_CLIENT_SECRET",
            "LINKEDIN_PERSONAL_ACCESS_TOKEN",
            "LINKEDIN_PERSONAL_URN",
        ),
        note="OAuth via scripts/oauth_linkedin_personal.py (token valable ~60j)",
    ),
    EnvGroup(
        key="linkedin_page",
        label="LinkedIn App #2 — Page Omnividens (bloqué CMA review)",
        required=(
            "LINKEDIN_PAGE_CLIENT_ID",
            "LINKEDIN_PAGE_CLIENT_SECRET",
            "LINKEDIN_PAGE_ACCESS_TOKEN",
            "LINKEDIN_PAGE_URN",
        ),
        optional=("LINKEDIN_PAGE_ID",),
        note="Bloqué tant que Community Management API pas approuvée",
    ),
    EnvGroup(
        key="stripe",
        label="Stripe (FinanceBot P7)",
        required=("STRIPE_SECRET_KEY", "STRIPE_WEBHOOK_SECRET"),
        optional=("FINANCEBOT_DUNNING_ENABLED",),
        note="Webhook secret = Stripe Dashboard → Developers → Webhooks",
    ),
    EnvGroup(
        key="outbound",
        label="Outbound (OutboundBot P13, shadow par défaut)",
        required=("OUTBOUND_UNSUBSCRIBE_SECRET",),
        optional=(
            "OUTBOUND_LIVE_MODE",
            "OUTBOUND_FROM_DOMAIN",
            "OUTBOUND_DAILY_MAX",
        ),
        note="LIVE_MODE=false jusqu'à warmup 4 semaines (~M6)",
    ),
    EnvGroup(
        key="google_ads",
        label="Google Ads (AdBot P12 live mode)",
        required=(
            "GOOGLE_ADS_DEVELOPER_TOKEN",
            "GOOGLE_ADS_CLIENT_ID",
            "GOOGLE_ADS_CLIENT_SECRET",
            "GOOGLE_ADS_REFRESH_TOKEN",
        ),
        note="Developer token = review Google ~7j (M7)",
    ),
    EnvGroup(
        key="meta_ads",
        label="Meta Ads (AdBot P12)",
        required=("META_ADS_ACCESS_TOKEN", "META_ADS_AD_ACCOUNT_ID"),
        note="System User long-lived token (M8)",
    ),
    EnvGroup(
        key="umami",
        label="Umami self-hosted (INFRA-02)",
        required=("UMAMI_BASE_URL", "UMAMI_USERNAME", "UMAMI_PASSWORD", "UMAMI_WEBSITE_ID"),
        note="Déploiement Docker analytics.omnividens.fr (M10)",
    ),
    EnvGroup(
        key="ops_dashboard",
        label="Admin Control Panel (P16)",
        required=(
            "OPS_DASHBOARD_BASIC_AUTH_USER",
            "OPS_DASHBOARD_BASIC_AUTH_PASSWORD",
            "OPS_DASHBOARD_JWT_SECRET",
        ),
        optional=("OPS_DASHBOARD_IP_ALLOWLIST", "OPS_DASHBOARD_TOTP_SECRET"),
        note="Caddy basic auth + IP allowlist côté serveur (M11)",
    ),
)


@dataclass
class GroupReport:
    group: EnvGroup
    required_present: list[str] = field(default_factory=list)
    required_missing: list[str] = field(default_factory=list)
    optional_present: list[str] = field(default_factory=list)
    optional_missing: list[str] = field(default_factory=list)

    @property
    def complete(self) -> bool:
        return not self.required_missing

    @property
    def status(self) -> str:
        if self.complete and self.required_present:
            return "READY"
        if not self.required_present and not self.optional_present:
            return "EMPTY"
        if self.required_missing:
            return "PARTIAL"
        return "READY"


def _is_set(value: str | None) -> bool:
    return value is not None and value.strip() != ""


def audit_group(group: EnvGroup) -> GroupReport:
    report = GroupReport(group=group)
    for var in group.required:
        if _is_set(os.environ.get(var)):
            report.required_present.append(var)
        else:
            report.required_missing.append(var)
    for var in group.optional:
        if _is_set(os.environ.get(var)):
            report.optional_present.append(var)
        else:
            report.optional_missing.append(var)
    return report


def render_human(reports: list[GroupReport]) -> str:
    lines: list[str] = []
    width = 70
    lines.append("=" * width)
    lines.append(" Argos Ops — audit env wiring (valeurs jamais affichées)")
    lines.append("=" * width)
    badges = {"READY": "[OK]    ", "PARTIAL": "[!]     ", "EMPTY": "[ ]     "}
    for report in reports:
        badge = badges.get(report.status, "[?]     ")
        lines.append(f"\n{badge}{report.group.label}")
        if report.group.note:
            lines.append(f"        {report.group.note}")
        for var in report.required_present:
            lines.append(f"          ✓ {var}")
        for var in report.required_missing:
            lines.append(f"          ✗ {var}  (REQUIRED)")
        for var in report.optional_present:
            lines.append(f"          ✓ {var}  (optional)")
        for var in report.optional_missing:
            lines.append(f"          · {var}  (optional, vide)")

    ready = sum(1 for r in reports if r.status == "READY")
    partial = sum(1 for r in reports if r.status == "PARTIAL")
    empty = sum(1 for r in reports if r.status == "EMPTY")
    lines.append("\n" + "=" * width)
    lines.append(f" Bilan : {ready} READY · {partial} PARTIAL · {empty} EMPTY")
    lines.append("=" * width)
    return "\n".join(lines)


def render_json(reports: list[GroupReport]) -> str:
    payload = [
        {
            "group": r.group.key,
            "label": r.group.label,
            "status": r.status,
            "complete": r.complete,
            "required_present": r.required_present,
            "required_missing": r.required_missing,
            "optional_present": r.optional_present,
            "optional_missing": r.optional_missing,
            "note": r.group.note,
        }
        for r in reports
    ]
    return json.dumps(payload, indent=2, ensure_ascii=False)


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="sortie JSON parseable")
    parser.add_argument(
        "--only",
        default="",
        help="filtre groupes par clé (comma-séparé), ex: --only linkedin_personal,stripe",
    )
    args = parser.parse_args()

    load_dotenv(".env.local")

    only_keys = {k.strip() for k in args.only.split(",") if k.strip()}
    selected = [g for g in GROUPS if not only_keys or g.key in only_keys]
    reports = [audit_group(g) for g in selected]

    if args.json:
        print(render_json(reports))
    else:
        print(render_human(reports))

    has_partial = any(r.status == "PARTIAL" for r in reports)
    return 1 if has_partial else 0


if __name__ == "__main__":
    sys.exit(main())
