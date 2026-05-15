"""Templates outbound : opt-out HMAC, footer RGPD, cadence séquence (P13).

Tout est déterministe et testable — pas d'appel LLM, pas d'IO. La
composition du body de chaque touche se fait ailleurs (slash command
+ skill ``outbound-drafter`` à venir).

Conformité (D-018, P17) :

- **Opt-out 1-clic** via lien signé HMAC-SHA256, vérifiable côté
  endpoint ``/unsubscribe`` (P13.B). Empêche la falsification du token
  par un tiers tout en restant stateless (pas besoin d'une table de
  tokens pré-générés).
- **Footer RGPD** mentionne intérêt légitime BtoB, durée de
  conservation, droit à l'effacement, contact DPO.
- **AI Act art. 50** — disclosure IA dans le footer (texte court venant
  des settings ``email_signature_ai_disclosure``).
"""

from __future__ import annotations

import hashlib
import hmac
import re
from datetime import date, timedelta
from urllib.parse import quote, urlencode

# =============================================================================
# Cadence séquence — 5 touches espacées sur ~30 jours
# =============================================================================
TOUCH_CADENCE_DAYS: list[int] = [0, 3, 7, 14, 30]
"""Offsets en jours depuis la 1re touche pour les 5 touches canoniques.

D+0 / D+3 / D+7 / D+14 / D+30. Calibré pour BtoB (vs BtoC qui est plus
serré, vs enterprise qui est plus large). Évite le ratio quotidien qui
augmente les taux de plainte spam.
"""


def compute_touch_dates(start_date: date) -> list[date]:
    """Calcule les dates absolues des 5 touches à partir de la date de départ.

    Pas de business-day skipping pour l'instant — l'envoi réel (P13.B)
    appliquera un décalage si la date tombe samedi/dimanche.
    """
    return [start_date + timedelta(days=offset) for offset in TOUCH_CADENCE_DAYS]


# =============================================================================
# Slug — identifiant court et stable pour un lead
# =============================================================================
_SLUG_RE = re.compile(r"[^a-z0-9-]+")


def slugify(full_name: str, domain: str) -> str:
    """Produit un slug kebab-case <50 chars depuis nom + domaine.

    Idempotent : ``slugify(slugify(x, y), z)`` est stable. Utilisé pour
    nommer les répertoires ``data/outbound/sequences/<slug>/`` et
    ``data/outbound/enriched/<slug>.md``.

    Exemple : ``slugify("Marc Dupont", "acme.fr") → "marc-dupont-acme-fr"``
    """
    raw = f"{full_name}-{domain}".lower().strip()
    # Remplace espaces et séparateurs courants par '-' avant suppression
    raw = re.sub(r"[\s._@]+", "-", raw)
    slug = _SLUG_RE.sub("-", raw).strip("-")
    # Compresse les '-' multiples
    slug = re.sub(r"-{2,}", "-", slug)
    return slug[:50]


# =============================================================================
# Opt-out — HMAC stateless
# =============================================================================
OPT_OUT_BASE_URL = "https://omnividens.fr/unsubscribe"
"""URL canonique de désinscription (endpoint à livrer en P13.B).

Conservée sur le domaine principal `omnividens.fr` même si l'envoi
outbound passe par un domaine secondaire — le destinataire fait
naturellement plus confiance au domaine officiel pour l'opt-out.
"""


def generate_opt_out_token(email: str, secret: str) -> str:
    """Génère un token HMAC-SHA256 hex 16 chars pour le lien d'opt-out.

    ``secret`` = ``OUTBOUND_UNSUBSCRIBE_SECRET`` (env var). Si le secret
    est rotaté, **tous** les anciens liens d'opt-out cessent de marcher
    — c'est volontaire (mécanisme de revocation globale).

    Le token est court (16 chars) pour rester URL-friendly. La fenêtre
    de collision sur 16 chars hex est de 2⁶⁴ — largement suffisant pour
    un usage non-cryptographique de lien email.
    """
    email_normalized = email.strip().lower().encode("utf-8")
    digest = hmac.new(secret.encode("utf-8"), email_normalized, hashlib.sha256).hexdigest()
    return digest[:16]


def verify_opt_out_token(email: str, token: str, secret: str) -> bool:
    """Vérifie un token d'opt-out en temps constant.

    ``hmac.compare_digest`` évite les timing attacks pour comparer le
    digest attendu vs le digest fourni. Toujours utiliser cette fonction
    côté endpoint ``/unsubscribe`` (P13.B) — jamais ``==``.
    """
    expected = generate_opt_out_token(email, secret)
    return hmac.compare_digest(expected, token)


def build_opt_out_url(email: str, secret: str) -> str:
    """Construit l'URL complète d'opt-out pour un email donné.

    Format : ``https://omnividens.fr/unsubscribe?email=...&t=...``

    Les deux paramètres ``email`` et ``t`` sont url-encodés. Le
    destinataire clique → endpoint vérifie le token → enregistre dans la
    table ``unsubscribes`` (migration P13.B) → 200 OK avec page de
    confirmation FR.
    """
    token = generate_opt_out_token(email, secret)
    params = urlencode({"email": email, "t": token}, quote_via=quote)
    return f"{OPT_OUT_BASE_URL}?{params}"


# =============================================================================
# Footer email — RGPD + AI Act + opt-out
# =============================================================================
OUTBOUND_FOOTER_TEMPLATE = (
    "\n\n---\n"
    "{tagline}\n"
    "{site_url}\n"
    "\n"
    "{ai_disclosure}\n"
    "\n"
    "Vous recevez ce message car votre profil correspond à notre cible BtoB "
    "(intérêt légitime — RGPD art. 6.1.f). Données conservées 12 mois max.\n"
    "Se désinscrire en 1 clic : {opt_out_url}\n"
)
"""Footer RGPD + AI Act + opt-out — pieds de TOUS les emails outbound.

Placeholders à remplir par ``build_footer()`` :

- ``{tagline}`` — ``EMAIL_SIGNATURE_TAGLINE`` (« Argos — on scanne, vous corrigez. »)
- ``{site_url}`` — ``EMAIL_SIGNATURE_SITE_URL`` (``https://omnividens.fr``)
- ``{ai_disclosure}`` — ``EMAIL_SIGNATURE_AI_DISCLOSURE`` (AI Act art. 50)
- ``{opt_out_url}`` — généré par ``build_opt_out_url(email, secret)``
"""


def build_footer(
    *,
    email: str,
    secret: str,
    tagline: str,
    site_url: str,
    ai_disclosure: str,
) -> str:
    """Compose le footer RGPD complet pour un destinataire donné."""
    return OUTBOUND_FOOTER_TEMPLATE.format(
        tagline=tagline,
        site_url=site_url,
        ai_disclosure=ai_disclosure,
        opt_out_url=build_opt_out_url(email, secret),
    )


__all__ = [
    "OPT_OUT_BASE_URL",
    "OUTBOUND_FOOTER_TEMPLATE",
    "TOUCH_CADENCE_DAYS",
    "build_footer",
    "build_opt_out_url",
    "compute_touch_dates",
    "generate_opt_out_token",
    "slugify",
    "verify_opt_out_token",
]
