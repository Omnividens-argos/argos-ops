"""Règles brand Argos / Omnividens consommées par BrandGuardBot.

Source vérité :

- Produit = **Argos**
- Entreprise = **Omnividens**
- Domaine canonique = ``omnividens.fr`` (jamais ``.com``)
- Tagline = ``Argos — on scanne, vous corrigez.``
- Disclosure AI Act art. 50 = ``Email rédigé par notre assistant Argos Ops.``
  (jamais "validé par humain" — c'est une affirmation non-vérifiable
  côté destinataire, ref. memory user 2026-05-08)

Le module expose :
- :func:`canonical_brand_rules` : liste des règles + sévérité
- :func:`audit_text` : applique les règles à un texte et retourne les
  :class:`BrandIssue` détectées
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

BRAND_TAGLINE = "Argos — on scanne, vous corrigez."
CANONICAL_DOMAIN = "omnividens.fr"
DISCLOSURE_PHRASE = "Email rédigé par notre assistant Argos Ops."


@dataclass
class BrandIssue:
    """Une violation de règle brand détectée dans un texte."""

    rule_id: str
    severity: str  # 'error' | 'warning' | 'info'
    message: str


@dataclass
class BrandRule:
    rule_id: str
    severity: str
    description: str
    pattern: re.Pattern[str] = field(repr=False)
    forbidden: bool = True  # True = match déclenche l'issue
    message_template: str = ""


def canonical_brand_rules() -> list[BrandRule]:
    """Liste des règles brand canoniques."""
    return [
        BrandRule(
            rule_id="domain_dot_com",
            severity="error",
            description="Le domaine est omnividens.fr, pas .com",
            pattern=re.compile(r"omnividens\.com", re.IGNORECASE),
            message_template="Domaine `omnividens.com` détecté — utiliser `omnividens.fr`.",
        ),
        BrandRule(
            rule_id="ai_validated_by_human",
            severity="error",
            description="L'AI Act interdit d'affirmer une validation humaine non-traçable",
            pattern=re.compile(r"validé\s+par\s+(un\s+)?humain", re.IGNORECASE),
            message_template=(
                "Phrase « validé par humain » détectée — non-vérifiable côté "
                "destinataire, contrevient à l'AI Act art. 50. Utiliser "
                f"`{DISCLOSURE_PHRASE}` à la place."
            ),
        ),
        BrandRule(
            rule_id="argos_lowercase",
            severity="warning",
            description="Le nom produit s'écrit Argos (capitale)",
            pattern=re.compile(r"\bargos\b"),
            message_template="`argos` en minuscules — préférer `Argos` (capitale).",
        ),
        BrandRule(
            rule_id="omnividens_lowercase",
            severity="warning",
            description="Le nom entreprise s'écrit Omnividens (capitale)",
            pattern=re.compile(r"\bomnividens\b"),
            message_template="`omnividens` en minuscules — préférer `Omnividens` (capitale).",
        ),
        BrandRule(
            rule_id="fud_words",
            severity="warning",
            description="Argos évite le FUD (Fear, Uncertainty, Doubt)",
            pattern=re.compile(r"\b(catastrophe|apocalyptique|terriblement)\b", re.IGNORECASE),
            message_template=(
                "Vocabulaire FUD détecté — Argos communique factuellement, "
                "pas par la peur."
            ),
        ),
    ]


def audit_text(text: str, rules: list[BrandRule] | None = None) -> list[BrandIssue]:
    """Détecte les violations des règles brand dans ``text``."""
    rules = rules or canonical_brand_rules()
    issues: list[BrandIssue] = []
    # Pour les rules de casse, on ne flag QUE si la version capitale est absente
    has_argos_caps = re.search(r"\bArgos\b", text) is not None
    has_omnividens_caps = re.search(r"\bOmnividens\b", text) is not None
    for rule in rules:
        if not rule.pattern.search(text):
            continue
        # Exception : si le texte contient déjà la version capitalisée, on
        # considère que la version minuscule est intentionnelle (URL, code…)
        if rule.rule_id == "argos_lowercase" and has_argos_caps:
            continue
        if rule.rule_id == "omnividens_lowercase" and has_omnividens_caps:
            continue
        if rule.forbidden:
            issues.append(
                BrandIssue(
                    rule_id=rule.rule_id,
                    severity=rule.severity,
                    message=rule.message_template or rule.description,
                )
            )
    return issues


__all__ = [
    "BRAND_TAGLINE",
    "CANONICAL_DOMAIN",
    "DISCLOSURE_PHRASE",
    "BrandIssue",
    "BrandRule",
    "audit_text",
    "canonical_brand_rules",
]
