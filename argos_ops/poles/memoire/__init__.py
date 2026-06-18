"""Pôle 7 — **Mémoire** (archi v2, S7).

Concierge de la mémoire de flotte. Agent particulier (déclenché par script, par
pôle) qui lit un pôle EN ENTIER, protège l'``important`` + les patterns, et
**propose** une liste « safe to delete » ; le script ``MemoryCleaner`` est le
**seul** bras autorisé à supprimer un fait, et n'exécute que la liste validée par
l'humain avec un double garde-fou. ``CapabilityRouter`` audite le câblage
``reads_cross_pole`` de la flotte. Tout est déterministe / fichier (D-017).

Modules :

- :mod:`~argos_ops.poles.memoire.policy` — ``policy.yaml`` (actif par pôle,
  patterns protégés, rétention).
- :mod:`~argos_ops.poles.memoire.curation` — logique pure du plan (invariant
  « l'important n'est jamais supprimable »).
- :mod:`~argos_ops.poles.memoire.cleaner` — exécution gardée + file validée.
- :mod:`~argos_ops.poles.memoire.history` — journal append-only des passages.
- :mod:`~argos_ops.poles.memoire.wiring` — audit du câblage inter-pôles.
- :mod:`~argos_ops.poles.memoire.agent` — :class:`MemoireAgent`.
"""

from __future__ import annotations

from argos_ops.poles.memoire.agent import MemoireAgent
from argos_ops.poles.memoire.curation import CurationPlan, plan_curation
from argos_ops.poles.memoire.policy import MemoryPolicy, load_policy

__all__ = [
    "CurationPlan",
    "MemoireAgent",
    "MemoryPolicy",
    "load_policy",
    "plan_curation",
]
