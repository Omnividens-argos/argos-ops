"""Pôle jouet ``_example`` — démonstration de référence du flux archi v2.

Prouve le contrat **script → mémoire → agent** :

1. :class:`~argos_ops.poles.example.scripts.heartbeat.HeartbeatScript` (bras
   déterministe) écrit un fait dans sa mémoire.
2. :class:`~argos_ops.poles.example.agent.ExampleAgent` (cerveau) charge son
   contexte (sa mémoire + cross-pôle déclaré) et **agit** dessus.

Ce pôle est *technique* (préfixe ``_``) : exclu des 8 onglets cockpit et de
:func:`argos_ops.poles.list_poles`. Il sert de gabarit copiable pour les
sessions S1-S6. Cf. ``scripts/poles_demo.py`` pour le lancer en vrai.
"""

from __future__ import annotations

from argos_ops.poles.example.agent import ExampleAgent
from argos_ops.poles.example.scripts.heartbeat import HeartbeatScript

EXAMPLE_POLE = "_example"

__all__ = ["EXAMPLE_POLE", "ExampleAgent", "HeartbeatScript"]
