"""Helpers de conformité RGPD / AI Act / Bloctel (P17 + P22.E).

Centralise les checks déterministes qu'on ne veut **pas** déléguer à un
LLM, parce qu'ils font partie du contrat légal avec l'utilisateur et
doivent être reproductibles à 100 %.

Premier check livré (P17, 2026-05-14) : :func:`is_human_response_requested`
— détecte qu'un email entrant demande explicitement une réponse humaine
(AI Act article 13 + notre engagement public ``data/legal/ai-disclosure.md``
§ 5.2). Quand le check est positif, EmailBot et ``/check-emails`` doivent
**court-circuiter** tout drafting IA et router en file Tier 2 humain.

Extensions P22.E (2026-05-23) — checks pour les watchers Compliance
(``RGPDAuditor``, ``AIActComplianceBot``, ``BloctelGuard``,
``ContractDeadlineBot``) :

- :func:`scan_pii_collectors` — regex sur fichiers Python, repère les
  motifs de collecte PII (email, téléphone, IP, etc.)
- :func:`classify_ai_act_risk` — normalise le tag ``ai_act_risk_class``
  d'un agent en niveau canonique AI Act
- :func:`normalize_phone_fr` — canonicalise un numéro FR pour comparaison
  Bloctel (format +33 sans espaces ni séparateurs)
- :func:`is_phone_on_bloctel` — check membership d'un numéro normalisé
  dans la liste mensuelle d'opposition
- :func:`next_renewal_date` — calcule la prochaine date d'anniversaire
  d'un contrat à partir de la date de signature + durée
- :func:`days_until` — utilitaire signed pour comparer deux dates

Tous les checks sont **déterministes** (pas d'appel LLM) et
**conservateurs** (préfèrent un faux positif).
"""

from __future__ import annotations

import calendar
import re
import unicodedata
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Literal

# Liste exhaustive des phrases déclencheuses. Synchronisée avec
# ``.claude/skills/email-classifier/SKILL.md`` § « Override AI Act § 5.2 ».
_HUMAN_REQUEST_PHRASES: tuple[str, ...] = (
    # FR
    "reponse humaine",
    "reponse par un humain",
    "reponse d'un humain",
    "un humain svp",
    "un humain s'il vous plait",
    "un humain s il vous plait",
    "pas de bot",
    "pas de chatbot",
    "pas d'ia",
    "pas d ia",
    "pas d'ai",
    "pas d ai",
    "parler a un humain",
    # EN
    "human reply",
    "human please",
    "talk to a human",
    "no bot",
    "no chatbot",
    "no ai",
    "speak to a human",
    "speak with a human",
)

_BODY_WINDOW_CHARS = 500


def _normalize(text: str) -> str:
    """Lowercase + retire les accents (NFD + drop combining marks)."""
    nfkd = unicodedata.normalize("NFKD", text)
    no_accents = "".join(c for c in nfkd if not unicodedata.combining(c))
    return no_accents.lower()


def is_human_response_requested(
    *,
    subject: str,
    body: str,
    body_window_chars: int = _BODY_WINDOW_CHARS,
) -> bool:
    """Retourne ``True`` si l'email demande explicitement une réponse humaine."""
    if not subject and not body:
        return False

    haystack_subject = _normalize(subject or "")
    haystack_body = _normalize((body or "")[:body_window_chars])
    haystack = f"{haystack_subject}\n{haystack_body}"

    for phrase in _HUMAN_REQUEST_PHRASES:
        normalized_phrase = _normalize(phrase)
        pattern = rf"(?:^|\W){re.escape(normalized_phrase)}(?:\W|$)"
        if re.search(pattern, haystack):
            return True
    return False


# =============================================================================
# P22.E — Scan PII pour RGPDAuditor
# =============================================================================
PIICategory = Literal["email", "phone", "ip_address", "name", "address", "id_card"]


@dataclass(frozen=True)
class PIIFinding:
    """Une occurrence de collecte PII détectée dans un fichier source."""

    path: Path
    line_no: int
    category: PIICategory
    snippet: str


_PII_PATTERNS: tuple[tuple[PIICategory, re.Pattern[str]], ...] = (
    ("email", re.compile(r"\b(email|e_mail|mail_address|courriel)\s*[:=]", re.IGNORECASE)),
    ("email", re.compile(r"EmailStr|email_validator", re.IGNORECASE)),
    ("phone", re.compile(r"\b(phone|telephone|mobile|tel_number)\s*[:=]", re.IGNORECASE)),
    ("ip_address", re.compile(r"\b(ip_address|client_ip|remote_addr|forwarded_for)\s*[:=]", re.IGNORECASE)),
    ("ip_address", re.compile(r"request\.client\.host|X-Forwarded-For", re.IGNORECASE)),
    ("name", re.compile(r"\b(first_name|last_name|full_name)\s*[:=]", re.IGNORECASE)),
    ("name", re.compile(r"\b(nom|prenom)\s*[:=]", re.IGNORECASE)),
    ("address", re.compile(r"\b(postal_address|street_address|zip_code|postal_code)\s*[:=]", re.IGNORECASE)),
    ("id_card", re.compile(r"\b(id_card|passport|national_id|cni)\s*[:=]", re.IGNORECASE)),
)


def scan_pii_collectors(path: Path) -> list[PIIFinding]:
    """Scan un fichier Python à la recherche de motifs de collecte PII.

    Conservateur : matche les noms de variables / champs qui suggèrent
    une collecte PII. Pas d'analyse sémantique — si un humain documente
    correctement la ligne dans le registre, le finding sera marqué
    comme couvert lors de la cross-reference.
    """
    if not path.exists() or path.suffix != ".py":
        return []
    findings: list[PIIFinding] = []
    try:
        content = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    for line_no, line in enumerate(content.splitlines(), start=1):
        if line.strip().startswith("#"):
            continue
        for category, pattern in _PII_PATTERNS:
            if pattern.search(line):
                findings.append(
                    PIIFinding(
                        path=path,
                        line_no=line_no,
                        category=category,
                        snippet=line.strip()[:120],
                    )
                )
                break
    return findings


# =============================================================================
# P22.E — Classification AI Act
# =============================================================================
AIActRisk = Literal["minimal", "limited", "high", "prohibited", "unclassified"]

_VALID_AI_ACT_CLASSES: frozenset[str] = frozenset(
    {"minimal", "limited", "high", "prohibited"}
)


def classify_ai_act_risk(raw: object) -> AIActRisk:
    """Normalise la valeur ``ai_act_risk_class`` d'un agent.

    Retourne ``"unclassified"`` si l'attribut est absent, ``None``, ou
    ne match aucune des 4 catégories canoniques de l'AI Act
    (minimal / limited / high / prohibited).
    """
    if not isinstance(raw, str):
        return "unclassified"
    normalized = raw.strip().lower()
    if normalized in _VALID_AI_ACT_CLASSES:
        return normalized  # type: ignore[return-value]
    return "unclassified"


# =============================================================================
# P22.E — Bloctel (loi BtoC 2014)
# =============================================================================
def normalize_phone_fr(raw: str) -> str | None:
    """Canonicalise un numéro FR au format +33XXXXXXXXX.

    Retourne ``None`` si le numéro n'est pas reconnaissable comme FR.
    """
    if not isinstance(raw, str):
        return None
    digits = re.sub(r"[\s.\-()]", "", raw)
    if digits.startswith("+33"):
        digits = "33" + digits[3:]
    elif digits.startswith("0033"):
        digits = "33" + digits[4:]
    elif digits.startswith("0") and len(digits) == 10:
        digits = "33" + digits[1:]
    if not digits.isdigit():
        return None
    if not digits.startswith("33") or len(digits) != 11:
        return None
    if digits[2] == "0":
        return None
    return "+" + digits


def is_phone_on_bloctel(phone: str, *, bloctel_list_path: Path) -> bool:
    """Vrai si ``phone`` apparaît dans la liste Bloctel.

    Si le fichier n'existe pas, retourne ``False`` — le watcher amont
    doit déjà alerter sur l'absence de liste.
    """
    normalized_target = normalize_phone_fr(phone)
    if normalized_target is None or not bloctel_list_path.exists():
        return False
    try:
        content = bloctel_list_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return False
    for line in content.splitlines():
        candidate = line.strip()
        if not candidate or candidate.startswith("#"):
            continue
        normalized_candidate = normalize_phone_fr(candidate)
        if normalized_candidate == normalized_target:
            return True
    return False


# =============================================================================
# P22.E — Renouvellements de contrats
# =============================================================================
def _last_day_of_month(year: int, month: int) -> int:
    return calendar.monthrange(year, month)[1]


def next_renewal_date(
    *, start: date, term_months: int, today: date
) -> date:
    """Retourne la prochaine date d'anniversaire d'un contrat.

    Lève ``ValueError`` si ``term_months <= 0``.
    """
    if term_months <= 0:
        raise ValueError("term_months doit être > 0")
    target = start
    while target <= today:
        total_months = target.month + term_months
        new_year = target.year + (total_months - 1) // 12
        new_month = ((total_months - 1) % 12) + 1
        day = min(target.day, _last_day_of_month(new_year, new_month))
        target = date(new_year, new_month, day)
    return target


def days_until(target: date, *, today: date) -> int:
    """Nombre de jours signed depuis ``today`` jusqu'à ``target``.

    Positif si futur, négatif si passé, 0 si égal.
    """
    return (target - today).days


__all__ = [
    "AIActRisk",
    "PIICategory",
    "PIIFinding",
    "classify_ai_act_risk",
    "days_until",
    "is_human_response_requested",
    "is_phone_on_bloctel",
    "next_renewal_date",
    "normalize_phone_fr",
    "scan_pii_collectors",
]
