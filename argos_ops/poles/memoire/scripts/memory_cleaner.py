"""``MemoryCleanerScript`` — exécute les suppressions **validées** (archi v2, S7).

Bras déterministe : rejoue les files validées déposées par le cockpit
(``data/poles/memoire/validated/<pole>.yaml``) via
:func:`~argos_ops.poles.memoire.cleaner.execute_cleanup` — donc avec les **deux
garde-fous** (re-lecture live + appartenance au plan) qui rendent tout fait
``important`` non supprimable. Vide la file traitée et écrit un fait de synthèse.
Skip silencieux si aucune file en attente. Seul bras de la flotte autorisé à
supprimer un fait.
"""

from __future__ import annotations

from argos_ops.poles.base import BaseScript, ScriptResult
from argos_ops.poles.memoire import cleaner
from argos_ops.poles.memoire.policy import load_policy
from argos_ops.poles.memory import MemoryRecord


class MemoryCleanerScript(BaseScript):
    """Exécute les files validées (suppression gardée) → fait ``cleanup``."""

    pole = "memoire"
    name = "memory_cleaner"

    async def run(self) -> ScriptResult:
        policy = load_policy(poles_root=self.poles_root)
        queue = cleaner.load_validated_queue(poles_root=self.poles_root)
        if not queue:
            return ScriptResult(status="success", summary="aucune file validée — skip", written=[])

        written: list[MemoryRecord] = []
        total_deleted = 0
        total_refused = 0
        for pole, targets in queue.items():
            result = await cleaner.execute_cleanup(
                pole,
                targets,
                policy=policy,
                actor="memory_cleaner",
                poles_root=self.poles_root,
            )
            # Ne vide la file que si quelque chose a abouti OU s'il n'y a rien à
            # retenter (aucun refus). Un run 100 % refusé (ex. pôle passé inactif
            # entre la validation cockpit et le cron) conserve la file pour retry —
            # on ne jette jamais silencieusement une liste validée par l'humain.
            if result.n_deleted > 0 or result.n_refused == 0:
                cleaner.clear_validated_queue(pole, poles_root=self.poles_root)
            total_deleted += result.n_deleted
            total_refused += result.n_refused
            body = (
                f"Cleanup « {pole} » : {result.n_deleted} supprimé(s), "
                f"{result.n_refused} refusé(s) sur {result.requested} validé(s)."
            )
            record = await self.write_memory(
                body, kind="cleanup", tags=("curation", pole), important=False
            )
            written.append(record)
        return ScriptResult(
            status="success",
            summary=f"{total_deleted} supprimé(s), {total_refused} refusé(s)",
            written=written,
        )


__all__ = ["MemoryCleanerScript"]
