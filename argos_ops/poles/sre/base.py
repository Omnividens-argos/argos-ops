"""Socle des scripts SRE : ``BaseSreScript`` + ``run_sre_script`` (archi v2, S8).

Le pôle SRE n'a aucun agent. Chaque bras est un :class:`BaseSreScript` qui
implémente un seul ``check()`` *pur* renvoyant un :class:`~argos_ops.poles.sre.report.SreReport`.
Le wrapper :func:`run_sre_script` centralise, pour **tous** les scripts du pôle :

1. la **garde kill-switch** (un script gelé ne tourne pas, run journalisé ``skipped``) ;
2. le **chronométrage** + capture d'exception (un check qui crashe → run ``failed``
   rouge, jamais d'exception qui remonte au cron) ;
3. l'**écriture mémoire** (1 fait stable par état, ``important`` si rouge) ;
4. la **ligne de journal** (:mod:`argos_ops.poles.sre.runlog`) qui alimente le
   statut temps réel, les perfs P50/P95 et l'historique du cockpit.

``BaseSreScript.run()`` (contrat ``BaseScript``) délègue à ``run_sre_script`` :
les scripts restent lançables via le ``run_script`` du socle (cron / orchestrateur).
"""

from __future__ import annotations

import contextlib
import time
from abc import abstractmethod
from datetime import UTC, datetime

from loguru import logger

from argos_ops.poles.base import BaseScript, ScriptResult
from argos_ops.poles.memory import MemoryRecord
from argos_ops.poles.sre.killswitch import load_killswitch
from argos_ops.poles.sre.report import SEVERITY_ORDER, Severity, SreReport
from argos_ops.poles.sre.runlog import RunLogEntry, append_run


class BaseSreScript(BaseScript):
    """Bras déterministe du pôle SRE. Les sous-classes déclarent ``name`` et
    implémentent :meth:`check`. ``pole`` est fixé à ``"sre"``.

    ``important_at`` : sévérité minimale à partir de laquelle le fait mémoire est
    protégé (``important=True``). Par défaut ``red`` — un constat rouge ne doit
    pas être élagué silencieusement par le pôle Mémoire.
    """

    pole = "sre"
    important_at: Severity = "red"

    @abstractmethod
    async def check(self) -> SreReport:
        """Logique de surveillance pure et idempotente. Ne fait aucune I/O mémoire."""

    async def run(self) -> ScriptResult:
        return await run_sre_script(self)

    async def persist(self, report: SreReport) -> MemoryRecord | None:
        """Écrit le constat en mémoire (corps stable ⇒ idempotent à état constant)."""
        important = SEVERITY_ORDER[report.severity] >= SEVERITY_ORDER[self.important_at]
        body = report.summary if not report.detail else f"{report.summary}\n\n{report.detail}"
        return await self.write_memory(
            body, kind=self.name, tags=("sre", report.severity), important=important
        )


async def run_sre_script(script: BaseSreScript, *, now: datetime | None = None) -> ScriptResult:
    """Exécute un script SRE de bout en bout (kill-switch → check → mémoire → journal)."""
    moment = now or datetime.now(UTC)
    ks = load_killswitch(poles_root=script.poles_root)
    if ks.is_frozen(script.name):
        logger.info(f"sre/{script.name} — gelé (kill-switch), run sauté")
        append_run(
            RunLogEntry(
                at=moment,
                script=script.name,
                status="skipped",
                severity="green",
                duration_ms=0.0,
                summary="kill-switch actif — run gelé",
            ),
            poles_root=script.poles_root,
        )
        return ScriptResult(status="skipped", summary="kill-switch actif — run gelé")

    started = time.monotonic()
    try:
        report = await script.check()
    except Exception as exc:
        duration_ms = (time.monotonic() - started) * 1000.0
        logger.exception(f"sre/{script.name} — check en échec")
        append_run(
            RunLogEntry(
                at=moment,
                script=script.name,
                status="failed",
                severity="red",
                duration_ms=duration_ms,
                summary=f"échec du check : {type(exc).__name__}",
                error=f"{type(exc).__name__}: {exc}",
            ),
            poles_root=script.poles_root,
        )
        return ScriptResult(status="failed", error=f"{type(exc).__name__}: {exc}")

    duration_ms = (time.monotonic() - started) * 1000.0
    # Garde symétrique du contrat « jamais d'exception qui remonte au cron » : un
    # échec d'écriture mémoire / journal (ValueError corps vide, OSError disque) ne
    # doit pas s'échapper même quand un appelant invoque run()/run_sre_script
    # directement (sans le garde-fou externe de run_script).
    try:
        record = await script.persist(report)
        append_run(
            RunLogEntry(
                at=moment,
                script=script.name,
                status="success",
                severity=report.severity,
                duration_ms=duration_ms,
                summary=report.summary,
            ),
            poles_root=script.poles_root,
        )
    except Exception as exc:
        logger.exception(f"sre/{script.name} — persist/journal en échec")
        with contextlib.suppress(Exception):
            append_run(
                RunLogEntry(
                    at=moment,
                    script=script.name,
                    status="failed",
                    severity="red",
                    duration_ms=duration_ms,
                    summary=f"échec persist/journal : {type(exc).__name__}",
                    error=f"{type(exc).__name__}: {exc}",
                ),
                poles_root=script.poles_root,
            )
        return ScriptResult(status="failed", error=f"{type(exc).__name__}: {exc}")
    logger.info(f"sre/{script.name} — {report.severity} : {report.summary}")
    return ScriptResult(
        status="success", summary=report.summary, written=[record] if record else []
    )


__all__ = ["BaseSreScript", "run_sre_script"]
