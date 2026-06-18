"""``BaseScript`` — le bras déterministe d'un pôle (socle archi v2).

Un **script** fait du travail *pur et déterministe* (fetch / calcul / action
idempotente) et **écrit sa propre mémoire**. Il ne décide rien, ne rédige rien :
c'est l'agent du pôle qui lit cette mémoire et agit (cf.
:mod:`argos_ops.poles.agent`).

Contrat ::

    class TrendSpotter(BaseScript):
        pole = "veille"
        name = "trend_spotter"

        async def run(self) -> ScriptResult:
            signaux = await self._fetch()                 # déterministe
            rec = await self.write_memory(                # écrit sa mémoire
                f"{len(signaux)} sujets chauds détectés",
                kind="signal", tags=("cyber",),
            )
            return ScriptResult(status="success", written=[rec])

:func:`run_script` enrobe l'exécution (log + exception → ``ScriptResult`` failed)
sans dépendre de la DB — les scripts sont local-first (D-017).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Literal

from loguru import logger

from argos_ops.poles import memory
from argos_ops.poles.config import POLES_DIR
from argos_ops.poles.memory import MemoryRecord

ScriptStatus = Literal["success", "failed", "skipped"]


@dataclass
class ScriptResult:
    """Résultat d'un run de script déterministe."""

    status: ScriptStatus
    summary: str | None = None
    error: str | None = None
    written: list[MemoryRecord] = field(default_factory=list)


class BaseScript(ABC):
    """Tout script (bras déterministe) d'un pôle hérite de cette classe.

    Les sous-classes déclarent ``pole`` et ``name`` (slugs), implémentent
    ``run()`` et écrivent leur mémoire via :meth:`write_memory` /
    :meth:`flag_important`. ``poles_root`` est injectable pour les tests
    (mémoire hermétique sous ``tmp_path``).
    """

    pole: str  # ex. "veille"
    name: str  # ex. "trend_spotter"

    def __init__(self, *, poles_root: Path = POLES_DIR) -> None:
        self.poles_root = poles_root

    @abstractmethod
    async def run(self) -> ScriptResult:
        """Logique déterministe — idempotente en cas de retry."""

    # --- primitives mémoire liées à CE script -------------------------------
    async def write_memory(
        self,
        body: str,
        *,
        kind: str = "note",
        tags: tuple[str, ...] = (),
        important: bool = False,
        source: str | None = None,
        created_at: datetime | None = None,
    ) -> MemoryRecord:
        """Écrit un fait dans la mémoire de ce script (idempotent)."""
        return await memory.write_memory(
            self.pole,
            self.name,
            body,
            kind=kind,
            tags=tags,
            important=important,
            source=source or self.name,
            created_at=created_at,
            poles_root=self.poles_root,
        )

    async def read_memory(self) -> list[MemoryRecord]:
        """Relit la mémoire de ce script (du plus récent au plus ancien)."""
        return await memory.read_memory(self.pole, self.name, poles_root=self.poles_root)

    async def flag_important(
        self, record_id: str, *, important: bool = True
    ) -> MemoryRecord | None:
        """Protège (ou dé-protège) un fait de ce script."""
        return await memory.flag_important(
            self.pole, self.name, record_id, important=important, poles_root=self.poles_root
        )


async def run_script(script: BaseScript) -> ScriptResult:
    """Enrobe l'exécution d'un script : log start → run → log end.

    N'écrit pas en DB (local-first). Capture toute exception et la convertit
    en ``ScriptResult`` ``failed`` pour qu'un cron SRE ne crashe jamais sur un
    script isolé.
    """
    logger.info(f"Script {script.pole}/{script.name} — start")
    try:
        result = await script.run()
    except Exception as exc:
        logger.exception(f"Script {script.pole}/{script.name} — failed")
        return ScriptResult(status="failed", error=f"{type(exc).__name__}: {exc}")
    logger.info(
        f"Script {script.pole}/{script.name} — {result.status} "
        f"({len(result.written)} fait(s) écrit(s))"
    )
    return result
