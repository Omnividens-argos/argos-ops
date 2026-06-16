"""Exceptions custom Argos Ops.

Convention CLAUDE.md : pas de ``raise Exception(...)`` brut dans les
agents — toutes les erreurs métier passent par une sous-classe de
:class:`ArgosOpsError` pour que :func:`run_agent` (cf.
``argos_ops.agents.base``) puisse les loguer proprement par type et que
``ErrorTriageBot`` puisse les regrouper par signature.

Hiérarchie ::

    ArgosOpsError                 # racine commune (tout est attrapable d'un coup)
    ├── AgentExecutionError       # raté pendant la phase métier d'un agent
    │   ├── AgentDataSourceError  # lecture DB / fichier YAML / API tierce KO
    │   └── AgentOutputError      # écriture du livrable a échoué (FS, Discord, etc.)
    └── ConfigError               # config manquante / invalide (env var, settings...)

Les agents lèvent ces exceptions ; ``run_agent`` les capture en haut de
stack, les loggue avec :func:`loguru.logger.exception`, écrit le run en
``failed`` dans ``agent_runs`` et retourne un :class:`RunResult` ``failed``.
"""

from __future__ import annotations


class ArgosOpsError(Exception):
    """Racine commune de toutes les erreurs métier Argos Ops."""


class AgentExecutionError(ArgosOpsError):
    """Erreur pendant la phase ``run()`` d'un agent.

    Sous-classes recommandées : :class:`AgentDataSourceError` (lecture
    KO) et :class:`AgentOutputError` (écriture KO). Utilise directement
    cette classe si l'erreur ne rentre ni dans l'une ni dans l'autre.
    """


class AgentDataSourceError(AgentExecutionError):
    """Échec de lecture d'une source (DB, fichier YAML, API tierce)."""


class AgentOutputError(AgentExecutionError):
    """Échec d'écriture du livrable (fichier disque, push Discord, etc.)."""


class ConfigError(ArgosOpsError):
    """Config manquante ou invalide (env var absente, valeur incohérente)."""


class CapabilityDeniedError(ArgosOpsError):
    """Un agent tente un ``write_back`` sans capability ``enabled`` (P21)."""


__all__ = [
    "AgentDataSourceError",
    "AgentExecutionError",
    "AgentOutputError",
    "ArgosOpsError",
    "CapabilityDeniedError",
    "ConfigError",
]
