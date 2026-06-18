"""Pôle 8 — **SRE / Meta-Ops** (archi v2, S8).

Santé de la flotte, **sans aucun agent LLM** : uniquement des bras déterministes
en cron auto (D-017, local-first). Chaque script implémente un ``check()`` pur et
le socle SRE en dérive un fait mémoire + une ligne de journal.

Couches du pôle :

- :mod:`~argos_ops.poles.sre.report` — sévérité (vert/jaune/rouge) + ``SreReport``.
- :mod:`~argos_ops.poles.sre.runlog` — journal append-only des runs (statut, perf).
- :mod:`~argos_ops.poles.sre.breakers` — registre fichier des circuit breakers.
- :mod:`~argos_ops.poles.sre.killswitch` — interrupteur d'arrêt de la flotte.
- :mod:`~argos_ops.poles.sre.schedule` — cadence cron (croniter) + planning flotte.
- :mod:`~argos_ops.poles.sre.base` — ``BaseSreScript`` + ``run_sre_script``.
- :mod:`~argos_ops.poles.sre.status` — tableau de statut temps réel du cockpit.
- :mod:`~argos_ops.poles.sre.orchestrator` — chef de fleet déterministe (plan/exec).
- :mod:`~argos_ops.poles.sre.scripts` — les 13 scripts watchers / auditeurs / générateurs.
"""

from __future__ import annotations

from argos_ops.poles.sre.base import BaseSreScript, run_sre_script
from argos_ops.poles.sre.orchestrator import (
    OrchestrationPlan,
    execute_plan,
    plan_execution,
)
from argos_ops.poles.sre.report import Severity, SreReport, worst
from argos_ops.poles.sre.scripts import RUNNABLE, SRE_SCRIPTS
from argos_ops.poles.sre.status import ScriptStatus, compute_status, fleet_health

__all__ = [
    "RUNNABLE",
    "SRE_SCRIPTS",
    "BaseSreScript",
    "OrchestrationPlan",
    "ScriptStatus",
    "Severity",
    "SreReport",
    "compute_status",
    "execute_plan",
    "fleet_health",
    "plan_execution",
    "run_sre_script",
    "worst",
]
