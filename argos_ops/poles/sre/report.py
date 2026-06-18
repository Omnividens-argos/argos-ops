"""Sévérité + rapport d'un check SRE (archi v2, S8).

Le pôle SRE n'a **aucun agent LLM** : chaque script est un bras déterministe qui
exécute un *check* et renvoie un :class:`SreReport` (vert / jaune / rouge + un
résumé stable). Le socle SRE (:mod:`argos_ops.poles.sre.base`) transforme ce
rapport en fait mémoire + ligne de journal (:mod:`argos_ops.poles.sre.runlog`).

``Severity`` est l'échelle commune à tout le pôle (statut live, watchdog,
breakers) ; :func:`worst` agrège plusieurs sévérités en gardant la plus grave.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Severity = Literal["green", "yellow", "red"]

# Ordre de gravité (croissant) — sert au calcul de la couleur globale.
SEVERITY_ORDER: dict[Severity, int] = {"green": 0, "yellow": 1, "red": 2}


def worst(*severities: Severity) -> Severity:
    """Renvoie la sévérité la plus grave (``red`` > ``yellow`` > ``green``).

    Sans argument ⇒ ``green`` (rien d'observé n'est un état sain par défaut).
    """
    out: Severity = "green"
    for sev in severities:
        if SEVERITY_ORDER[sev] > SEVERITY_ORDER[out]:
            out = sev
    return out


def at_least(severity: Severity, threshold: Severity) -> bool:
    """``True`` si ``severity`` est au moins aussi grave que ``threshold``."""
    return SEVERITY_ORDER[severity] >= SEVERITY_ORDER[threshold]


@dataclass(frozen=True)
class SreReport:
    """Résultat d'un check SRE.

    - ``severity`` : couleur du *constat* (un check peut s'exécuter parfaitement
      — ``status`` success — et constater un état ``red``, ex. backup manquant).
    - ``summary`` : 1 ligne **stable** (sans horodatage / durée) → l'écriture
      mémoire reste idempotente tant que l'état observé ne change pas.
    - ``detail`` : corps markdown optionnel (lui aussi stable) joint au fait.
    """

    severity: Severity
    summary: str
    detail: str = ""

    @property
    def should_alert(self) -> bool:
        """Un constat non vert mérite d'être remonté (cockpit / mémoire importante)."""
        return self.severity != "green"


__all__ = [
    "SEVERITY_ORDER",
    "Severity",
    "SreReport",
    "at_least",
    "worst",
]
