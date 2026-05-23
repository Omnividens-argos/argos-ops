"""Templates Markdown pour devis, contrats et mails post-démo.

Pas de moteur de template lourd (Jinja2) — on utilise ``str.format``
sur des constantes Markdown. Lisible, reviewable, versionnable en clair.

PDF (P22.H : ProposalBot / ContractGenerator) : on tente d'utiliser
``pandoc`` via ``subprocess`` s'il est disponible sur le PATH. Sinon
on retourne le Markdown brut et on laisse le fondateur convertir à la
main. Pas de dépendance Python ajoutée (WeasyPrint / ReportLab) pour
respecter D-009.
"""

from __future__ import annotations

import shutil
import subprocess
from datetime import date, timedelta
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from argos_ops.sales.models import ProposalContext

PROPOSAL_TEMPLATE = """---
title: "Devis — {plan}"
author: "Omnividens (Argos)"
date: "{issue_date}"
---

# Devis Argos — {company}

**Date d'émission :** {issue_date}
**Valide jusqu'au :** {valid_until}
**Contact :** {contact_name} <{contact_email}>
{siret_line}

## Offre

| Item | Quantité | Prix unitaire (€ HT) | Total HT |
|---|---|---|---|
| {plan} — abonnement mensuel | 12 mois | {monthly_price_eur} € | {annual_subscription} € |
| Frais d'installation | 1 | {setup_fee_eur} € | {setup_fee_eur} € |
{discount_row}
| **Total HT première année** | | | **{total_ht} €** |
| TVA 20 % | | | {tva} € |
| **Total TTC** | | | **{total_ttc} €** |

## Conditions

- Durée d'engagement : {contract_duration_months} mois
- Paiement : mensuel par carte (Stripe) ou prélèvement SEPA
- Mise en service : dans les 5 jours ouvrés après signature
- CGV applicables : version disponible sur https://omnividens.fr/cgv

Pour accepter ce devis, renvoyez-le signé à
{contact_email} ou via le lien Stripe qui suivra.

---
*Argos — on scanne, vous corrigez.*
https://omnividens.fr
"""


CONTRACT_TEMPLATE = """---
title: "Contrat de prestation — {plan}"
author: "Omnividens (Argos)"
date: "{issue_date}"
---

# Contrat de prestation Argos

**Entre les soussignés :**

**Omnividens SAS** (« le Prestataire »), dont le siège est en France,
représentée par son représentant légal.

**et**

**{company}** (« le Client »), représenté par {contact_name},
contact : {contact_email}{siret_clause}.

## Article 1 — Objet

Le Prestataire fournit au Client l'accès à la plateforme Argos
(plan {plan}) et les services associés, dans les conditions définies
ci-après.

## Article 2 — Durée

Le contrat est conclu pour une durée de {contract_duration_months} mois
à compter de la date de signature, renouvelable par tacite reconduction
sauf dénonciation 60 jours avant l'échéance.

## Article 3 — Prix et conditions de paiement

L'abonnement mensuel s'élève à **{monthly_price_eur} € HT** par mois
(soit {annual_subscription} € HT par an). Les frais d'installation
s'élèvent à **{setup_fee_eur} € HT**.

Total première année : **{total_ht} € HT** ({total_ttc} € TTC).
{discount_clause}
Paiement mensuel automatique via Stripe ou prélèvement SEPA.

## Article 4 — Conformité

Le Prestataire respecte le RGPD (responsable de traitement)
et l'AI Act (transparence sur les agents IA exposés au Client).
Une analyse d'impact (DPIA) peut être fournie sur demande.

## Article 5 — Loi applicable et juridiction

Le présent contrat est soumis au droit français. Tout litige sera
porté devant les tribunaux compétents du ressort du siège du
Prestataire.

---

Fait à _______________, le {issue_date}.

**Le Client**                          **Le Prestataire**
Nom : ____________                     Omnividens SAS
Signature :                            Signature :


---
*Argos — on scanne, vous corrigez.*
https://omnividens.fr
"""


DEMO_FOLLOWUP_TEMPLATE = """Bonjour {first_name},

Merci pour le temps qu'on a passé ensemble {when_clause}. Récap des
points qui sont sortis pendant la démo :

{pain_points_block}

Voici ce qu'on a convenu pour la suite :

{next_steps_block}

Comme promis, je joins {attachments_clause}. Je reste dispo si tu
veux qu'on creuse {focus_topic} avant {next_milestone}.

Bonne semaine,

Le fondateur d'Omnividens
"""


def _money(value: float) -> int:
    """Arrondi entier (devis = pas de centimes)."""
    return round(value)


def render_proposal(context: ProposalContext) -> str:
    """Génère le Markdown d'un devis depuis un ``ProposalContext``."""
    annual_subscription = _money(context.monthly_price_eur * 12)
    subtotal = annual_subscription + context.setup_fee_eur
    if context.discount_percent > 0:
        discount_amount = _money(subtotal * context.discount_percent / 100)
        total_ht = subtotal - discount_amount
        discount_row = (
            f"| Remise commerciale ({context.discount_percent} %) | | | -{discount_amount} € |\n"
        )
    else:
        total_ht = subtotal
        discount_row = ""
    tva = _money(total_ht * 0.20)
    total_ttc = total_ht + tva
    valid_until = context.issue_date + timedelta(days=context.validity_days)
    siret_line = f"**SIRET :** {context.siret}\n" if context.siret else ""

    return PROPOSAL_TEMPLATE.format(
        plan=context.plan,
        company=context.company,
        contact_name=context.contact_name,
        contact_email=context.contact_email,
        siret_line=siret_line,
        issue_date=context.issue_date.isoformat(),
        valid_until=valid_until.isoformat(),
        monthly_price_eur=context.monthly_price_eur,
        annual_subscription=annual_subscription,
        setup_fee_eur=context.setup_fee_eur,
        discount_row=discount_row,
        total_ht=total_ht,
        tva=tva,
        total_ttc=total_ttc,
        contract_duration_months=context.contract_duration_months,
    )


def render_contract(context: ProposalContext) -> str:
    """Génère le Markdown d'un contrat / MSA depuis un ``ProposalContext``."""
    annual_subscription = _money(context.monthly_price_eur * 12)
    subtotal = annual_subscription + context.setup_fee_eur
    if context.discount_percent > 0:
        discount_amount = _money(subtotal * context.discount_percent / 100)
        total_ht = subtotal - discount_amount
        discount_clause = (
            f"\nUne remise commerciale de {context.discount_percent} % "
            f"(soit -{discount_amount} €) s'applique sur la première année.\n"
        )
    else:
        total_ht = subtotal
        discount_clause = ""
    total_ttc = total_ht + _money(total_ht * 0.20)
    siret_clause = f", SIRET {context.siret}" if context.siret else ""

    return CONTRACT_TEMPLATE.format(
        plan=context.plan,
        company=context.company,
        contact_name=context.contact_name,
        contact_email=context.contact_email,
        siret_clause=siret_clause,
        issue_date=context.issue_date.isoformat(),
        contract_duration_months=context.contract_duration_months,
        monthly_price_eur=context.monthly_price_eur,
        annual_subscription=annual_subscription,
        setup_fee_eur=context.setup_fee_eur,
        total_ht=total_ht,
        total_ttc=total_ttc,
        discount_clause=discount_clause,
    )


def render_demo_followup(
    *,
    first_name: str,
    when: date,
    pain_points: list[str],
    next_steps: list[tuple[str, str]],
    attachments: list[str],
    focus_topic: str,
    next_milestone: str,
) -> str:
    """Génère le draft mail récap post-démo."""
    when_clause = f"le {when.isoformat()}"
    if not pain_points:
        pain_block = "- (pas de pain points formalisés — à compléter à la main)"
    else:
        pain_block = "\n".join(f"- {p}" for p in pain_points)
    if not next_steps:
        next_block = "- (next steps à compléter à la main)"
    else:
        next_block = "\n".join(f"- **{owner}** : {action}" for owner, action in next_steps)
    if attachments:
        attachments_clause = "en pièces jointes : " + ", ".join(attachments)
    else:
        attachments_clause = "(rien à joindre cette fois)"
    return DEMO_FOLLOWUP_TEMPLATE.format(
        first_name=first_name,
        when_clause=when_clause,
        pain_points_block=pain_block,
        next_steps_block=next_block,
        attachments_clause=attachments_clause,
        focus_topic=focus_topic,
        next_milestone=next_milestone,
    )


def try_render_pdf(markdown_path: Path, *, pdf_path: Path) -> bool:
    """Tente une conversion Markdown → PDF via ``pandoc`` si dispo.

    Retourne ``True`` si le PDF a été généré, ``False`` si pandoc est
    absent (l'appelant garde alors le Markdown comme livrable et
    informe le fondateur).

    Pourquoi pandoc et pas WeasyPrint : pandoc est l'outil standard
    multi-OS pour Markdown → PDF/DOCX, dispo en single binary, et
    accepte LaTeX templates si on veut polisher visuellement plus
    tard (sans toucher au code Python). Conformité D-009 (0 dépendance
    Python ajoutée).
    """
    if shutil.which("pandoc") is None:
        return False
    try:
        subprocess.run(
            [
                "pandoc",
                str(markdown_path),
                "-o",
                str(pdf_path),
                "--pdf-engine=xelatex",
                "-V",
                "geometry:margin=2cm",
            ],
            check=True,
            capture_output=True,
            timeout=30,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        # xelatex absent → tente sans pdf-engine (HTML→PDF via wkhtmltopdf
        # ou autre fallback pandoc trouvera).
        try:
            subprocess.run(
                ["pandoc", str(markdown_path), "-o", str(pdf_path)],
                check=True,
                capture_output=True,
                timeout=30,
            )
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            return False
    return pdf_path.exists()


__all__ = [
    "CONTRACT_TEMPLATE",
    "DEMO_FOLLOWUP_TEMPLATE",
    "PROPOSAL_TEMPLATE",
    "render_contract",
    "render_demo_followup",
    "render_proposal",
    "try_render_pdf",
]
