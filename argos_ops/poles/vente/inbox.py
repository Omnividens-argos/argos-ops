"""Inbox du pôle Vente (archi v2, S4) — tri déterministe + gate AI Act.

Charge les messages entrants ``data/poles/vente/inbox/messages.yaml`` (ingérés à
la main ou par un futur connecteur IMAP, D-018) et les **classe** par mots-clés
en ``lead_chaud / question_tech / sav / partenariat / recrutement / presse /
spam / autre`` — port heuristique du skill ``email-classifier`` (sous D-017 le
fallback Python est la source de vérité testable).

Garde-fou conformité (AI Act art. 13 / § 5.2) : si un message demande
explicitement une réponse humaine
(:func:`argos_ops.compliance.is_human_response_requested`), le drafting IA est
**court-circuité** — Python tranche, on route en file humaine. Cf.
:func:`draft_reply` qui refuse de drafter dans ce cas.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Literal

import yaml

from argos_ops.compliance import is_human_response_requested
from argos_ops.poles.config import POLES_DIR
from argos_ops.poles.vente.store import parse_date, write_markdown

VENTE_POLE = "vente"

Category = Literal[
    "lead_chaud",
    "question_tech",
    "sav",
    "partenariat",
    "recrutement",
    "presse",
    "spam",
    "autre",
]

CATEGORIES: tuple[Category, ...] = (
    "lead_chaud",
    "question_tech",
    "sav",
    "partenariat",
    "recrutement",
    "presse",
    "spam",
    "autre",
)

# Catégories qui méritent une alerte (important=True en mémoire / rouge cockpit).
HOT_CATEGORIES: frozenset[str] = frozenset({"lead_chaud", "sav"})

# Mots-clés par catégorie — testés dans l'ordre de la liste (priorité décroissante).
# Le bruit (recrutement/presse/partenariat) est testé AVANT lead/sav pour éviter
# qu'une candidature « intéressé par votre poste » soit prise pour un lead chaud.
_RULES: tuple[tuple[Category, tuple[str, ...]], ...] = (
    ("spam", ("viagra", "crypto", "casino", "loan", "bitcoin", "prince", "gagné", "loterie")),
    (
        "recrutement",
        (
            "candidature",
            "cv",
            "alternance",
            "stage",
            "recrut",
            "spontanée",
            "rejoindre votre équipe",
        ),
    ),
    ("presse", ("journaliste", "presse", "interview", "rédaction", "média", "tribune", "podcast")),
    (
        "partenariat",
        ("partenariat", "partner", "revendeur", "affiliation", "intégrateur", "co-marketing"),
    ),
    (
        "lead_chaud",
        (
            "devis",
            "tarif",
            "prix",
            "démo",
            "demo",
            "essai",
            "acheter",
            "souscrire",
            "intéressé",
            "rendez-vous",
            "rdv",
        ),
    ),
    (
        "sav",
        (
            "bug",
            "erreur",
            "ne marche pas",
            "ne fonctionne",
            "facture",
            "remboursement",
            "résilier",
            "annuler",
            "incident",
            "problème",
        ),
    ),
    (
        "question_tech",
        (
            "comment",
            "scan",
            "api",
            "intégration",
            "fonctionnalité",
            "documentation",
            "configurer",
            "?",
        ),
    ),
)


@dataclass(frozen=True)
class InboundMessage:
    """Un message entrant à trier (saisi/ingéré dans messages.yaml)."""

    id: str
    from_email: str
    from_name: str
    subject: str
    body: str
    received_at: date
    status: str = "new"  # new | drafted | answered | archived
    category_override: Category | None = None  # tri manuel du fondateur

    @property
    def category(self) -> Category:
        """Catégorie effective : override humain prioritaire, sinon heuristique."""
        return self.category_override or classify(self.subject, self.body)

    @property
    def human_requested(self) -> bool:
        """``True`` si le message exige une réponse humaine (gate AI Act)."""
        return is_human_response_requested(subject=self.subject, body=self.body)


def classify(subject: str, body: str) -> Category:
    """Classe un message par mots-clés (sujet + corps). Défaut : ``autre``."""
    haystack = f"{subject}\n{body}".lower()
    for category, keywords in _RULES:
        if any(kw in haystack for kw in keywords):
            return category
    return "autre"


def messages_path(*, poles_root: Path = POLES_DIR) -> Path:
    return poles_root / VENTE_POLE / "inbox" / "messages.yaml"


def drafts_dir(*, poles_root: Path = POLES_DIR) -> Path:
    return poles_root / VENTE_POLE / "inbox" / "drafts"


def load_messages(*, poles_root: Path = POLES_DIR) -> list[InboundMessage]:
    """Charge les messages, du plus récent au plus ancien. Absent ⇒ ``[]``."""
    path = messages_path(poles_root=poles_root)
    if not path.exists():
        return []
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    entries = raw.get("messages", []) if isinstance(raw, dict) else []
    out: list[InboundMessage] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        override_raw = entry.get("category_override")
        override: Category | None = override_raw if override_raw in CATEGORIES else None
        out.append(
            InboundMessage(
                id=str(entry["id"]),
                from_email=str(entry.get("from_email", "")),
                from_name=str(entry.get("from_name", "")),
                subject=str(entry.get("subject", "")),
                body=str(entry.get("body", "")),
                received_at=parse_date(entry.get("received_at") or date.today().isoformat()),
                status=str(entry.get("status", "new")),
                category_override=override,
            )
        )
    out.sort(key=lambda m: m.received_at, reverse=True)
    return out


def _save_messages(messages: list[InboundMessage], *, poles_root: Path = POLES_DIR) -> None:
    payload = {
        "messages": [
            {
                "id": m.id,
                "from_email": m.from_email,
                "from_name": m.from_name,
                "subject": m.subject,
                "body": m.body,
                "received_at": m.received_at.isoformat(),
                "status": m.status,
                "category_override": m.category_override,
            }
            for m in messages
        ]
    }
    path = messages_path(poles_root=poles_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, allow_unicode=True, sort_keys=False), encoding="utf-8")


class HumanResponseRequiredError(Exception):
    """Levée quand un message exige une réponse humaine (gate AI Act)."""


def draft_reply(message_id: str, *, poles_root: Path = POLES_DIR) -> Path | None:
    """Drafte un squelette de réponse pour un message classé.

    Renvoie ``None`` si le message est introuvable. **Lève**
    :class:`HumanResponseRequiredError` si le message demande une réponse humaine —
    Python tranche, aucun draft IA n'est produit (AI Act). Idempotent : ré-écrit
    le même draft et flippe le statut à ``drafted``.
    """
    messages = load_messages(poles_root=poles_root)
    target = next((m for m in messages if m.id == message_id), None)
    if target is None:
        return None
    if target.human_requested:
        raise HumanResponseRequiredError(
            f"Message {message_id} demande une réponse humaine — drafting IA gelé (AI Act)."
        )

    draft_path = drafts_dir(poles_root=poles_root) / f"{message_id}.md"
    write_markdown(
        draft_path,
        {
            "message_id": message_id,
            "to": target.from_email,
            "category": target.category,
            "subject": f"Re: {target.subject}",
            "status": "draft",
            "drafted_at": datetime.now(UTC).isoformat(),
        },
        body=(
            f"Bonjour {target.from_name or ''},\n\n"
            "(brouillon à compléter — réutilise la KB Argos via le skill support-rag "
            "pour les questions tech, ou le ton commercial pour un lead.)\n\n"
            "Argos — on scanne, vous corrigez.\n"
        ),
    )
    updated = [
        InboundMessage(
            id=m.id,
            from_email=m.from_email,
            from_name=m.from_name,
            subject=m.subject,
            body=m.body,
            received_at=m.received_at,
            status="drafted" if m.id == message_id else m.status,
            category_override=m.category_override,
        )
        for m in messages
    ]
    _save_messages(updated, poles_root=poles_root)
    return draft_path


__all__ = [
    "CATEGORIES",
    "HOT_CATEGORIES",
    "Category",
    "HumanResponseRequiredError",
    "InboundMessage",
    "classify",
    "draft_reply",
    "drafts_dir",
    "load_messages",
    "messages_path",
]
