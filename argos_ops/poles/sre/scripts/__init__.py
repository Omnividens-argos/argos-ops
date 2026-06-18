"""Les 13 bras déterministes du pôle SRE (archi v2, S8).

Watchers (santé/uptime/SSL/DNS), auditeurs (deps/CVE, secrets, backups, flaky CI,
dérive de config) et générateurs (diagrammes, ADR). Chacun hérite de
:class:`~argos_ops.poles.sre.base.BaseSreScript` et implémente un ``check()`` pur.

``SRE_SCRIPTS`` est l'ordre canonique (= ``pole.yaml``) ; ``RUNNABLE`` est le
registre id → classe que l'orchestrateur instancie pour exécuter un script.
"""

from __future__ import annotations

from argos_ops.poles.sre.base import BaseSreScript
from argos_ops.poles.sre.scripts.adr_writer import AdrWriterScript
from argos_ops.poles.sre.scripts.backup_verifier import BackupVerifierScript
from argos_ops.poles.sre.scripts.bot_config_manager import BotConfigManagerScript
from argos_ops.poles.sre.scripts.ci_flake_tracker import CiFlakeTrackerScript
from argos_ops.poles.sre.scripts.dependency_auditor import DependencyAuditorScript
from argos_ops.poles.sre.scripts.diagram_generator import DiagramGeneratorScript
from argos_ops.poles.sre.scripts.dns_guard import DnsGuardScript
from argos_ops.poles.sre.scripts.doc_linter import DocLinterScript
from argos_ops.poles.sre.scripts.fleet_watchdog import FleetWatchdogScript
from argos_ops.poles.sre.scripts.kill_switch_operator import KillSwitchOperatorScript
from argos_ops.poles.sre.scripts.secret_rotator import SecretRotatorScript
from argos_ops.poles.sre.scripts.ssl_expirer import SslExpirerScript
from argos_ops.poles.sre.scripts.uptime_monitor import UptimeMonitorScript

# Ordre = ordre de déclaration dans data/poles/sre/pole.yaml.
SRE_SCRIPTS: tuple[type[BaseSreScript], ...] = (
    FleetWatchdogScript,
    UptimeMonitorScript,
    SslExpirerScript,
    DnsGuardScript,
    DependencyAuditorScript,
    SecretRotatorScript,
    BackupVerifierScript,
    CiFlakeTrackerScript,
    BotConfigManagerScript,
    DocLinterScript,
    DiagramGeneratorScript,
    AdrWriterScript,
    KillSwitchOperatorScript,
)

# Registre id → classe exécutable (constructeur acceptant uniquement poles_root).
RUNNABLE: dict[str, type[BaseSreScript]] = {cls.name: cls for cls in SRE_SCRIPTS}

__all__ = [
    "RUNNABLE",
    "SRE_SCRIPTS",
    "AdrWriterScript",
    "BackupVerifierScript",
    "BotConfigManagerScript",
    "CiFlakeTrackerScript",
    "DependencyAuditorScript",
    "DiagramGeneratorScript",
    "DnsGuardScript",
    "DocLinterScript",
    "FleetWatchdogScript",
    "KillSwitchOperatorScript",
    "SecretRotatorScript",
    "SslExpirerScript",
    "UptimeMonitorScript",
]
