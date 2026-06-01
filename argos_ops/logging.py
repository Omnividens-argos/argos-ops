"""Configuration loguru — filtre anti-fuite secrets sur les logs.

Filtre les patterns connus de credentials avant écriture (stdout / fichier
/ webhook). Cf. ``CLAUDE.md`` § Sécurité des secrets.

Patterns redactés (case-sensitive sauf mention) :

- ``https://discord.com/api/webhooks/<id>/<token>`` — webhook Discord
- ``sk-...`` — clé OpenAI / Anthropic API
- ``AIza...`` — clé Google API (Gemini, Maps, etc.)
- ``gho_...`` / ``ghp_...`` / ``ghs_...`` — token GitHub
- ``xoxb-.../xoxp-...`` — token Slack
- ``whsec_...`` — secret webhook Stripe
- ``WPL_AP1_...`` — token Discord client (legacy, conservé par sécurité)
- ``AKIA...`` + secret 40 chars — clé AWS
- ``eyJ....eyJ....sig`` — JWT (couvre les access tokens AT Protocol Bluesky
  + tout Bearer LinkedIn/Mastodon qui fuiterait)
- ``xxxx-xxxx-xxxx-xxxx`` — app password Bluesky (Settings → App Passwords)
- ``EAA...`` — token Meta / Facebook Graph API (page/user access token)

À installer **avant** tout autre import qui pourrait logger : appeler
:func:`install_secret_filter` au tout début de ``argos_ops/__init__.py``.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Final

from loguru import logger

if TYPE_CHECKING:
    from loguru import Record

# Ordre : du plus spécifique au plus générique. Chaque entrée = (regex, replacement).
# On garde une trace courte (8 premiers chars) pour pouvoir corréler entre logs
# sans pour autant exposer le secret complet.
_PATTERNS: Final[list[tuple[re.Pattern[str], str]]] = [
    # Webhooks Discord — URL complète à redacter en gardant l'ID (public)
    (
        re.compile(r"https://discord\.com/api/webhooks/(\d+)/[\w-]+"),
        r"https://discord.com/api/webhooks/\1/[REDACTED]",
    ),
    # Clés Anthropic / OpenAI (sk-...)
    (re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"), "sk-[REDACTED]"),
    # Clés Google API (AIza...)
    (re.compile(r"\bAIza[A-Za-z0-9_-]{30,}\b"), "AIza[REDACTED]"),
    # Tokens GitHub
    (re.compile(r"\bgh[osup]_[A-Za-z0-9]{30,}\b"), "gh_[REDACTED]"),
    # Tokens Slack
    (re.compile(r"\bxox[bpsa]-[A-Za-z0-9-]{20,}\b"), "xox_[REDACTED]"),
    # Secrets webhook Stripe
    (re.compile(r"\bwhsec_[A-Za-z0-9]{20,}\b"), "whsec_[REDACTED]"),
    # Tokens Discord client legacy (préfixe documenté CLAUDE.md)
    (re.compile(r"\bWPL_AP1_[A-Za-z0-9_-]{20,}\b"), "WPL_AP1_[REDACTED]"),
    # AWS access keys (AKIA + 16 chars)
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "AKIA[REDACTED]"),
    # JWT (3 segments base64url séparés par '.') — access tokens AT Protocol
    # Bluesky + tout Bearer LinkedIn/Mastodon. Préfixe eyJ = base64 de '{"'.
    (
        re.compile(r"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+"),
        "eyJ[REDACTED-JWT]",
    ),
    # App password Bluesky : 4 groupes de 4 alphanum séparés par '-'.
    (
        re.compile(r"\b[a-z0-9]{4}-[a-z0-9]{4}-[a-z0-9]{4}-[a-z0-9]{4}\b"),
        "[REDACTED-BSKY-APPPW]",
    ),
    # Tokens Meta / Facebook Graph API (préfixe EAA, page/user access token).
    # Inclure '_' et '-' : les vrais tokens Meta en contiennent — sinon la
    # redaction s'arrête au 1er séparateur et la queue du token fuiterait.
    (re.compile(r"\bEAA[A-Za-z0-9_-]{20,}"), "EAA[REDACTED-META]"),
]


def _redact(value: str) -> str:
    """Applique tous les patterns en cascade. Pure fonction, testable."""
    for pattern, replacement in _PATTERNS:
        value = pattern.sub(replacement, value)
    return value


def _patch_record(record: Record) -> bool:
    """Filtre loguru — modifie ``record`` in place. Retourne True (laisse passer).

    On patch uniquement ``message``. La trace stack des exceptions est gérée par
    le wrapper du sink dans :func:`install_secret_filter` (qui passe la chaîne
    finale formatée par ``_redact`` avant ``print``).
    """
    record["message"] = _redact(record["message"])
    return True


def install_secret_filter() -> None:
    """Reconfigure loguru : tous les sinks passent par le filtre redact.

    Idempotent — appel multiple OK (logger.remove() retire l'ancien handler).
    """
    logger.remove()
    logger.add(
        sink=lambda msg: print(_redact(msg), end=""),
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}",
        backtrace=True,
        diagnose=False,  # diagnose=True peut révéler des values dans les frames — désactivé pour sécurité
        filter=_patch_record,
    )


__all__ = ["install_secret_filter"]
