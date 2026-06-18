"""Bras déterministes (scripts) du pôle Mémoire (archi v2, S7).

- :class:`MemorySweepScript` (``memory_scan``) — réveille le ``MemoireAgent`` par
  pôle actif → propose un plan de curation (fait ``curation-plan``).
- :class:`MemoryCleanerScript` (``memory_cleaner``) — exécute les files validées
  (suppression gardée, seul bras autorisé à supprimer un fait).
- :class:`CapabilityRouterScript` (``capability_router``) — audite le câblage
  ``reads_cross_pole`` de la flotte.

100 % fichiers / local-first (D-017).
"""

from __future__ import annotations

from argos_ops.poles.memoire.scripts.capability_router import CapabilityRouterScript
from argos_ops.poles.memoire.scripts.memory_cleaner import MemoryCleanerScript
from argos_ops.poles.memoire.scripts.memory_scan import MemorySweepScript

# Ordre = ordre d'exécution cron canonique du pôle (scan → cleaner → audit).
MEMOIRE_SCRIPTS = (
    MemorySweepScript,
    MemoryCleanerScript,
    CapabilityRouterScript,
)

__all__ = [
    "MEMOIRE_SCRIPTS",
    "CapabilityRouterScript",
    "MemoryCleanerScript",
    "MemorySweepScript",
]
