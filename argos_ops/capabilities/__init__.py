"""Capabilities inter-agents — câblage pull-based (P21, file-based / D-033).

Couche fine au-dessus de la mémoire de flotte ([`fleet_memory`]) : déclare
**qui peut consommer quoi** chez les autres bots, avec filtres (kind / tags)
et toggle ``enabled``. Deux permissions :

- ``read`` — un bot tire les faits d'un autre bot pour enrichir son contexte
  (défaut **ALLOW** dérivé du graphe d'accès ``MEMORY.md`` ; une règle
  ``enabled: false`` agit en **deny override**) ;
- ``write_back`` — un bot dépose un fait ``advice.*`` dans la mémoire d'un
  autre, que celui-ci lira à son prochain run (défaut **DENY** : exige une
  règle ``enabled: true`` explicite, sinon :class:`CapabilityDeniedError`).

Pourquoi file-based et non la migration DB du plan (P21.A) : **D-028** a
rendu la mémoire 100 % fichiers, abandonnant la DB ``memory_items`` dont
P21.A dépendait. Le graphe d'accès encode déjà les permissions ``read`` —
ce module ajoute juste les filtres + ``write_back`` + l'audit. Cf. **D-033**.
"""

from __future__ import annotations

from argos_ops.capabilities.consume import consume_capabilities, write_back
from argos_ops.capabilities.loader import (
    DEFAULT_CAPABILITIES_PATH,
    effective_read_rules,
    load_capabilities,
)
from argos_ops.capabilities.models import CapabilityPermission, CapabilityRule

__all__ = [
    "DEFAULT_CAPABILITIES_PATH",
    "CapabilityPermission",
    "CapabilityRule",
    "consume_capabilities",
    "effective_read_rules",
    "load_capabilities",
    "write_back",
]
