"""Templates email CS — onboarding J+0/J+7/J+30, NPS, review request (P22.G).

Templates statiques (pas de LLM call) — la personnalisation se fait via
variables Python. Le founder peut éditer le draft à la main avant envoi
via ``zimbra-ops``. Signature Argos collée par
``argos_ops.outbound.templates.render_signature`` côté EmailBot quand
disponible — ici on garde la signature minimale (le founder peaufine).
"""

from __future__ import annotations

from datetime import date

ONBOARDING_DAY_0 = 0
ONBOARDING_DAY_7 = 7
ONBOARDING_DAY_30 = 30


def render_onboarding_email(
    *,
    contact_first_name: str,
    company: str,
    plan: str,
    step: int,
    signup_date: date,
) -> tuple[str, str]:
    """Renvoie ``(subject, body)`` pour un email d'onboarding J+0/7/30.

    J+0 — bienvenue + premier scan à lancer
    J+7 — check premier scan + lever blocages
    J+30 — bilan + propose call si NPS bas / pas d'usage
    """
    addressee = contact_first_name.strip() or "à vous"

    if step == ONBOARDING_DAY_0:
        subject = f"Bienvenue chez Argos — {company}"
        body = (
            f"Bonjour {addressee},\n\n"
            f"Bienvenue chez Argos. Votre compte ({plan}) est actif depuis aujourd'hui.\n\n"
            f"Première chose à faire : lancez un scan sur votre domaine principal "
            f"depuis https://omnividens.fr/app/scans/new. Ça prend 2-5 minutes selon "
            f"la taille du périmètre.\n\n"
            f"Je vous envoie un check J+7 pour voir où vous en êtes — si vous bloquez "
            f"avant, répondez à ce mail directement.\n\n"
            f"À très vite,\n"
            f"Le fondateur d'Omnividens"
        )
        return subject, body

    if step == ONBOARDING_DAY_7:
        subject = f"J+7 — votre premier scan Argos a bien tourné, {company} ?"
        body = (
            f"Bonjour {addressee},\n\n"
            f"Ça fait une semaine que votre compte Argos est actif (signup le "
            f"{signup_date.isoformat()}).\n\n"
            f"Trois questions rapides — répondez juste oui/non :\n"
            f"  1. Vous avez lancé au moins un scan ?\n"
            f"  2. Le rapport était lisible (priorités claires) ?\n"
            f"  3. Vous avez identifié au moins une vulnérabilité à corriger ?\n\n"
            f"Si vous bloquez sur l'un de ces trois points, je débloque en 15 min "
            f"de call — proposez un créneau et je m'aligne.\n\n"
            f"À très vite,\n"
            f"Le fondateur d'Omnividens"
        )
        return subject, body

    if step == ONBOARDING_DAY_30:
        subject = f"J+30 — bilan onboarding Argos pour {company}"
        body = (
            f"Bonjour {addressee},\n\n"
            f"Un mois s'est écoulé depuis votre arrivée chez Argos. Petit bilan :\n\n"
            f"- Combien de scans avez-vous lancés ce mois-ci ?\n"
            f"- Combien de vulnérabilités traitées / archivées ?\n"
            f"- Qu'est-ce qui vous manque pour aller plus vite ?\n\n"
            f"Si tout roule, je vous enverrai un NPS rapide dans quelques jours. "
            f"Si quelque chose coince, répondez à ce mail — on cale un call court.\n\n"
            f"Merci de votre confiance,\n"
            f"Le fondateur d'Omnividens"
        )
        return subject, body

    raise ValueError(f"step inconnu : {step} (attendu 0 / 7 / 30)")


def render_nps_email(*, contact_first_name: str, company: str, reason: str) -> tuple[str, str]:
    """Renvoie ``(subject, body)`` pour une demande NPS.

    ``reason`` ∈ {``onboarding_done``, ``renew``} — change le pitch.
    """
    addressee = contact_first_name.strip() or "à vous"
    if reason == "onboarding_done":
        subject = f"Argos — 1 question rapide ({company})"
        intro = (
            "Vous avez fini l'onboarding Argos il y a peu, et j'aimerais "
            "savoir comment ça se passe pour vous."
        )
    elif reason == "renew":
        subject = f"Argos — renouvellement = bonne occasion pour 1 question ({company})"
        intro = (
            "Votre abonnement Argos vient d'être renouvelé — merci de "
            "renouveler votre confiance. Avant qu'on reparte sur une nouvelle année, "
            "j'aimerais avoir votre ressenti."
        )
    else:
        raise ValueError(f"reason inconnu : {reason} (attendu onboarding_done / renew)")

    body = (
        f"Bonjour {addressee},\n\n"
        f"{intro}\n\n"
        f"Sur une échelle de 0 à 10, à quel point recommanderiez-vous Argos "
        f"à un pair (collègue, autre RSSI, autre fondateur) ?\n\n"
        f"- 0-6 : pas du tout / pas sûr\n"
        f"- 7-8 : oui mais avec réserves\n"
        f"- 9-10 : oui sans hésiter\n\n"
        f"Une note + 1 phrase d'explication suffit. Si vous mettez moins de 7, "
        f"je vous appelle dans la semaine pour comprendre — promis, pas de relance "
        f"automatique.\n\n"
        f"Merci d'avance,\n"
        f"Le fondateur d'Omnividens"
    )
    return subject, body


def render_review_email(*, contact_first_name: str, company: str) -> tuple[str, str]:
    """Renvoie ``(subject, body)`` pour une demande d'avis G2 / Capterra."""
    addressee = contact_first_name.strip() or "à vous"
    subject = f"Argos — 5 min pour aider d'autres RSSI à choisir ?"
    body = (
        f"Bonjour {addressee},\n\n"
        f"Vous utilisez Argos depuis un moment chez {company} — merci pour la "
        f"confiance.\n\n"
        f"Si Argos vous a fait gagner du temps ou clarifié votre posture sécu, "
        f"un avis public aiderait beaucoup d'autres RSSI à se décider :\n\n"
        f"- G2 : https://www.g2.com/products/argos-sechunter/reviews/new\n"
        f"- Capterra : https://www.capterra.fr/software/argos-sechunter/reviews/new\n\n"
        f"Comptez 5 minutes max. Pas de filtre côté Argos — même un avis 4/5 "
        f"avec 1 reproche est utile (et pour moi aussi, ça remonte du signal).\n\n"
        f"Pas de relance ; un seul mail, c'est promis.\n\n"
        f"Merci d'avance,\n"
        f"Le fondateur d'Omnividens"
    )
    return subject, body


__all__ = [
    "ONBOARDING_DAY_0",
    "ONBOARDING_DAY_30",
    "ONBOARDING_DAY_7",
    "render_nps_email",
    "render_onboarding_email",
    "render_review_email",
]
