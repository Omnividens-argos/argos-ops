"""Socle archi v2 — modèle **pôle / agent / script** d'Argos Ops.

Vocabulaire :

- **SCRIPT** (:class:`~argos_ops.poles.base.BaseScript`) — bras déterministe
  (fetch / calcul / action). Écrit sa propre mémoire fichier.
- **AGENT** (:class:`~argos_ops.poles.agent.BaseAgent`) — cerveau LLM, 1 par
  pôle. Lit la mémoire de ses scripts + celle des pôles déclarés cross-pôle,
  puis **agit** (décide / rédige / publie). Dispose d'une banque de skills.
- **MÉMOIRE** (:mod:`argos_ops.poles.memory`) — ``data/poles/<pole>/scripts/
  <script>/memory/``, 1 fait = 1 fichier, flag ``important`` protégeable.
- **pole.yaml** (:mod:`argos_ops.poles.config`) — déclare ``agent``,
  ``scripts``, ``reads_cross_pole``, ``front_tools``.

Les 8 pôles : Veille · Marketing/Comm · Pub · Vente&RC · Finance&Conformité ·
Direction · Mémoire · SRE/Meta-Ops.

Réutilisé par chaque pôle (sessions S1-S8) — ne dépend ni de la DB ni d'aucune
API tierce (D-017).
"""

from __future__ import annotations

from argos_ops.poles.agent import AgentContext, AgentResult, AgentStatus, BaseAgent
from argos_ops.poles.base import BaseScript, ScriptResult, ScriptStatus, run_script
from argos_ops.poles.config import (
    CROSS_POLE_WILDCARD,
    POLES_DIR,
    AgentSpec,
    PoleConfig,
    ScriptSpec,
    list_poles,
    load_all_poles,
    load_pole_config,
    pole_config_path,
    pole_dir,
)
from argos_ops.poles.memory import (
    MemoryRecord,
    compute_record_id,
    flag_important,
    read_memory,
    read_pole_memory,
    script_memory_dir,
    write_memory,
)

__all__ = [
    "CROSS_POLE_WILDCARD",
    # config / pole.yaml
    "POLES_DIR",
    "AgentContext",
    "AgentResult",
    "AgentSpec",
    "AgentStatus",
    # agent
    "BaseAgent",
    # script
    "BaseScript",
    # memory
    "MemoryRecord",
    "PoleConfig",
    "ScriptResult",
    "ScriptSpec",
    "ScriptStatus",
    "compute_record_id",
    "flag_important",
    "list_poles",
    "load_all_poles",
    "load_pole_config",
    "pole_config_path",
    "pole_dir",
    "read_memory",
    "read_pole_memory",
    "run_script",
    "script_memory_dir",
    "write_memory",
]
