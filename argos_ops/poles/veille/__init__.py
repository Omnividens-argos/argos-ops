"""Pôle 1 — **Veille** (archi v2, session S1).

Veille marché, tech, concurrents et menaces. Le pôle est **en amont** de la
flotte : ses 9 scripts (bras déterministes) captent des signaux publics et
écrivent leur mémoire ; le :class:`VeilleAgent` (cerveau) les synthétise en
insights actionnables routés vers Marketing / Pub / Vente.

Scripts (cf. :mod:`argos_ops.poles.veille.scripts`) :

- ``trend_spotter`` — sujets cyber chauds (fenêtre 14j)
- ``competitor_watcher`` — diff pages pricing/features concurrents
- ``breach_watcher`` — breaches publics croisés avec le carnet client
- ``regulatory_watcher`` — flux RSS RGPD / AI Act / NIS2 / DORA
- ``cve_monitor`` — CVE HIGH/CRITICAL sur les stacks clients déclarées
- ``darkweb_monitor`` — domaines clients dans les breaches publiques (HIBP)
- ``press_monitor`` — mentions presse Argos / Omnividens
- ``keyword_radar`` — mouvements de positions SERP prioritaires
- ``intent_signals`` — signaux d'achat publics (breach / CISO / levées)

Le câblage (``pole.yaml``, mémoire) suit le socle archi v2
(:mod:`argos_ops.poles`).
"""

from __future__ import annotations

from argos_ops.poles.veille.agent import VeilleAgent
from argos_ops.poles.veille.insights import (
    Insight,
    record_severity,
    routing_for,
    synthesize_insights,
)

VEILLE_POLE = "veille"

__all__ = [
    "VEILLE_POLE",
    "Insight",
    "VeilleAgent",
    "record_severity",
    "routing_for",
    "synthesize_insights",
]
