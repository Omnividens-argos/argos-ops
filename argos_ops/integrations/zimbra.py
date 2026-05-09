"""Wrapper IMAP/SMTP pour boîte OVH Zimbra (D-018).

Stack standard OVH Zimbra :
- IMAP SSL : ``ssl0.ovh.net:993``
- SMTP SSL : ``ssl0.ovh.net:465``

L'API publique du module est :

- :class:`EmailMessage` — DTO pour un email lu en INBOX
- :func:`fetch_unread` — pull async des emails non lus
- :func:`mark_seen` — positionne ``\\Seen`` sur un UID
- :func:`send_email` — envoi SMTP SSL (texte ou multipart text+html)

``imap-tools`` est synchrone : on l'enrobe dans :func:`asyncio.to_thread` pour
ne pas bloquer la boucle. ``aiosmtplib`` est async natif.

Aucun appel LLM ici (D-017). Ce module ne fait que de la plomberie email.
"""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from email.message import EmailMessage as StdEmailMessage
from email.utils import getaddresses, parseaddr
from typing import cast

import aiosmtplib
from imap_tools import AND, MailBox
from loguru import logger
from pydantic import SecretStr


# =============================================================================
# DTO
# =============================================================================
@dataclass(frozen=True)
class EmailMessage:
    """Email lu sur IMAP, normalisé.

    ``uid`` est l'identifiant IMAP côté serveur (string), stable tant que
    l'email reste dans la même boîte. À utiliser pour :func:`mark_seen`.
    """

    uid: str
    from_email: str
    from_name: str | None
    to: list[str]
    subject: str
    body_text: str
    body_html: str | None
    date: datetime | None
    message_id: str | None
    in_reply_to: str | None
    references: list[str]


# =============================================================================
# Helpers
# =============================================================================
NOREPLY_PATTERNS: tuple[str, ...] = (
    "noreply@",
    "no-reply@",
    "donotreply@",
    "do-not-reply@",
    "mailer-daemon@",
    "postmaster@",
    "bounces@",
    "bounce@",
)


def is_noreply(from_email: str) -> bool:
    """Détecte les expéditeurs auto à ne jamais re-contacter."""
    addr = from_email.lower().strip()
    return any(pattern in addr for pattern in NOREPLY_PATTERNS)


def extract_domain(email_addr: str) -> str | None:
    """Retourne le domaine d'une adresse email, ou ``None`` si invalide."""
    addr = email_addr.lower().strip()
    if "@" not in addr:
        return None
    domain = addr.rsplit("@", 1)[1].strip("> ")
    return domain or None


# =============================================================================
# IMAP — fetch_unread + mark_seen
# =============================================================================
def _fetch_unread_sync(
    *, host: str, port: int, user: str, password: str, limit: int
) -> list[EmailMessage]:
    """Implémentation sync — exécutée dans un thread via :func:`asyncio.to_thread`."""
    out: list[EmailMessage] = []
    with MailBox(host, port=port).login(user, password, initial_folder="INBOX") as mailbox:
        for msg in mailbox.fetch(AND(seen=False), limit=limit, mark_seen=False):
            from_name, from_email = parseaddr(msg.from_)
            to_addrs = [addr for _, addr in getaddresses(msg.to) if addr]
            # imap_tools.LazyHeaders étend Mapping mais n'est pas paramétré,
            # donc mypy considère .get() comme untyped. On cast en Mapping
            # typé pour récupérer le checking strict ailleurs.
            headers = cast(Mapping[str, tuple[str, ...]], msg.headers)
            references_raw = headers.get("references", ())
            references_str = references_raw[0] if references_raw else ""
            references = [r for r in references_str.split() if r] if references_str else []

            message_id = headers.get("message-id", (None,))[0]
            in_reply_to = headers.get("in-reply-to", (None,))[0]

            out.append(
                EmailMessage(
                    uid=msg.uid or "",
                    from_email=from_email or "",
                    from_name=from_name or None,
                    to=to_addrs,
                    subject=msg.subject or "",
                    body_text=msg.text or "",
                    body_html=msg.html or None,
                    date=msg.date,
                    message_id=message_id,
                    in_reply_to=in_reply_to,
                    references=references,
                )
            )
    return out


async def fetch_unread(
    *,
    host: str,
    port: int,
    user: str,
    password: SecretStr,
    limit: int = 50,
) -> list[EmailMessage]:
    """Pull async des emails non lus (flag ``\\Seen=False``) sur INBOX.

    Le flag ``\\Seen`` n'est PAS positionné automatiquement — appeler
    :func:`mark_seen` après ingestion réussie pour fermer la boucle.

    ``limit`` plafonne le nombre d'emails par run pour éviter qu'une boîte
    qui a accumulé sature la cron.
    """
    return await asyncio.to_thread(
        _fetch_unread_sync,
        host=host,
        port=port,
        user=user,
        password=password.get_secret_value(),
        limit=limit,
    )


def _mark_seen_sync(*, host: str, port: int, user: str, password: str, uid: str) -> None:
    with MailBox(host, port=port).login(user, password, initial_folder="INBOX") as mailbox:
        mailbox.flag([uid], "\\Seen", True)


async def mark_seen(*, host: str, port: int, user: str, password: SecretStr, uid: str) -> None:
    """Positionne le flag IMAP ``\\Seen`` sur un email."""
    await asyncio.to_thread(
        _mark_seen_sync,
        host=host,
        port=port,
        user=user,
        password=password.get_secret_value(),
        uid=uid,
    )


# =============================================================================
# SMTP — send_email
# =============================================================================
async def send_email(
    *,
    host: str,
    port: int,
    user: str,
    password: SecretStr,
    from_name: str,
    to: str,
    subject: str,
    body_text: str,
    body_html: str | None = None,
    in_reply_to: str | None = None,
    references: list[str] | None = None,
) -> None:
    """Envoi SMTP SSL (port 465 chez OVH Zimbra).

    Si ``body_html`` est fourni, l'email est multipart ``alternative``.
    ``in_reply_to`` et ``references`` permettent de threader proprement
    une réponse à un message reçu.
    """
    msg = StdEmailMessage()
    msg["From"] = f'"{from_name}" <{user}>'
    msg["To"] = to
    msg["Subject"] = subject
    if in_reply_to:
        msg["In-Reply-To"] = in_reply_to
    if references:
        msg["References"] = " ".join(references)

    msg.set_content(body_text)
    if body_html:
        msg.add_alternative(body_html, subtype="html")

    await aiosmtplib.send(
        msg,
        hostname=host,
        port=port,
        username=user,
        password=password.get_secret_value(),
        use_tls=True,
        timeout=30,
    )
    logger.info(f"Email envoyé à {to} — sujet: {subject[:60]}")


__all__ = [
    "NOREPLY_PATTERNS",
    "EmailMessage",
    "extract_domain",
    "fetch_unread",
    "is_noreply",
    "mark_seen",
    "send_email",
]
