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
# Signature email — cohérente sur tous les envois Argos Ops
# =============================================================================
SIGNATURE_SEPARATOR_TEXT = "\n--\n"
SIGNATURE_SEPARATOR_HTML = '<hr style="border:none;border-top:1px solid #ddd;margin:16px 0;">'


_BRAND_HEADER = "[ ARGOS // OMNIVIDENS ]"


def _strip_brand_prefix(tagline: str) -> str:
    """Retire le préfixe ``Argos —`` ou ``Argos -`` d'une tagline pour
    éviter la redondance avec le header ``[ ARGOS // OMNIVIDENS ]`` du
    design brutaliste mono.
    """
    cleaned = tagline.strip()
    # Couvre EM DASH (canonique) + hyphen-minus (clavier sans touche EM DASH)
    for prefix in ("Argos — ", "Argos - "):
        if cleaned.startswith(prefix):
            return cleaned.removeprefix(prefix)
    return cleaned


def build_signature_text(
    *, contact_email: str, tagline: str, site_url: str, ai_disclosure: str
) -> str:
    """Bloc signature en texte brut (placé après ``--`` séparateur).

    Format brutaliste mono cohérent avec :func:`build_signature_html`.
    """
    short_tagline = _strip_brand_prefix(tagline)
    return (
        f"{_BRAND_HEADER}\n"
        f"> {short_tagline}\n"
        f"> {contact_email}\n"
        f"> {site_url}\n"
        f"\n"
        f"# {ai_disclosure}\n"
    )


def build_signature_html(
    *,
    contact_email: str,
    tagline: str,
    site_url: str,
    ai_disclosure: str,
) -> str:
    """Bloc signature HTML — design ``brutaliste mono`` validé 2026-05-09.

    Style ``terminal vibe`` : police monospace, fond grisé clair, header
    entre crochets, lignes préfixées ``>``, disclosure préfixée ``#``.
    Palette cohérente avec ``docs/UI_DECISIONS.md`` (zinc + accent sky-500
    sur les liens uniquement).
    """
    site_label = site_url.replace("https://", "").replace("http://", "").rstrip("/")
    short_tagline = _strip_brand_prefix(tagline)
    return (
        '<div style="font-family:ui-monospace,SFMono-Regular,Menlo,Monaco,'
        "Consolas,'Liberation Mono','Courier New',monospace;font-size:12px;"
        "color:#18181b;line-height:1.7;background:#fafafa;padding:14px 16px;"
        'border:1px solid #e4e4e7;display:inline-block;">'
        f'<div style="font-weight:700;color:#18181b;letter-spacing:0.5px;">'
        f"{_BRAND_HEADER}</div>"
        f'<div style="color:#52525b;">&gt; {short_tagline}</div>'
        '<div style="color:#52525b;margin-top:4px;">'
        f'&gt; <a href="mailto:{contact_email}" '
        'style="color:#0ea5e9;text-decoration:none;">'
        f"{contact_email}</a></div>"
        '<div style="color:#52525b;">'
        f'&gt; <a href="{site_url}" style="color:#0ea5e9;text-decoration:none;">'
        f"{site_label}</a></div>"
        f'<div style="color:#a1a1aa;margin-top:8px;"># {ai_disclosure}</div>'
        "</div>"
    )


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
    include_signature: bool = True,
    signature_tagline: str | None = None,
    signature_site_url: str | None = None,
    signature_ai_disclosure: str | None = None,
) -> None:
    """Envoi SMTP SSL (port 465 chez OVH Zimbra).

    Si ``body_html`` est fourni, l'email est multipart ``alternative``.
    ``in_reply_to`` et ``references`` permettent de threader proprement
    une réponse à un message reçu.

    ``include_signature`` (default True) appose la signature canonique
    (tagline + contact + AI Act disclosure) en bas du corps. Désactiver
    pour les transactionnels Stripe / signaux internes (P7+).
    """
    if include_signature:
        # Defaults (cohérents avec ``argos_ops.config.Settings``) — passés
        # explicitement par l'appelant pour ne pas re-importer Settings ici
        # (zimbra.py reste réutilisable hors contexte Argos Ops si besoin)
        tagline = signature_tagline or "Argos — on scanne, vous corrigez."
        site_url = signature_site_url or "https://omnividens.fr"
        disclosure = signature_ai_disclosure or "Email rédigé par notre assistant Argos Ops."
        sig_text = build_signature_text(
            contact_email=user,
            tagline=tagline,
            site_url=site_url,
            ai_disclosure=disclosure,
        )
        sig_html = build_signature_html(
            contact_email=user,
            tagline=tagline,
            site_url=site_url,
            ai_disclosure=disclosure,
        )
        body_text = body_text.rstrip() + SIGNATURE_SEPARATOR_TEXT + sig_text
        # Toujours générer un body_html quand on appose la signature, même si
        # l'appelant n'en a pas fourni : on convertit le texte (échappé +
        # sauts de ligne) en HTML minimal pour que la signature stylée
        # s'affiche dans Gmail / Outlook / Apple Mail.
        if body_html is None:
            from html import escape as html_escape

            html_body_lines = "<br>\n".join(
                html_escape(line)
                for line in body_text.split(SIGNATURE_SEPARATOR_TEXT)[0].split("\n")
            )
            body_html = (
                '<div style="font-family:-apple-system,BlinkMacSystemFont,'
                "'Segoe UI',Roboto,Helvetica,Arial,sans-serif;font-size:14px;"
                'color:#27272a;line-height:1.6;">'
                f"{html_body_lines}"
                "</div>"
            )
        body_html = body_html + SIGNATURE_SEPARATOR_HTML + sig_html

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
    "SIGNATURE_SEPARATOR_HTML",
    "SIGNATURE_SEPARATOR_TEXT",
    "EmailMessage",
    "build_signature_html",
    "build_signature_text",
    "extract_domain",
    "fetch_unread",
    "is_noreply",
    "mark_seen",
    "send_email",
]
