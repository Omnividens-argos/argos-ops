"""``MemorySweepScript`` — déclencheur de l'agent Mémoire (archi v2, S7).

Bras déterministe qui **réveille le** :class:`~argos_ops.poles.memoire.agent.MemoireAgent`
**par pôle actif** (cf. ``policy.active_for``) : pour chacun, il calcule le plan de
curation proposé et écrit un fait ``kind="curation-plan"`` dans sa propre mémoire
(snapshot du périmé/stale détecté). Ne supprime rien — c'est ``MemoryCleaner`` qui
exécute la liste **validée** par l'humain. Idempotent : à état mémoire inchangé,
le corps du fait est identique ⇒ même fichier (pas de doublon).
"""

from __future__ import annotations

from argos_ops.poles.base import BaseScript, ScriptResult
from argos_ops.poles.memoire.agent import MemoireAgent
from argos_ops.poles.memoire.policy import load_policy
from argos_ops.poles.memory import MemoryRecord


class MemorySweepScript(BaseScript):
    """Scanne chaque pôle actif → fait ``curation-plan`` (proposition, pas d'action)."""

    pole = "memoire"
    name = "memory_scan"

    async def run(self) -> ScriptResult:
        policy = load_policy(poles_root=self.poles_root)
        if not policy.active_for:
            return ScriptResult(
                status="success", summary="aucun pôle actif (policy) — skip", written=[]
            )
        written: list[MemoryRecord] = []
        total_candidates = 0
        for pole in policy.active_for:
            agent = MemoireAgent(pole, poles_root=self.poles_root, policy=policy)
            plan = await agent.build_plan()
            if plan.scanned == 0:
                continue
            total_candidates += plan.n_delete
            body = (
                f"Plan de curation « {pole} » : {plan.n_delete} fait(s) safe-to-delete "
                f"sur {plan.scanned} scanné(s) ({plan.n_important} important(s) protégé(s), "
                f"{plan.n_saved_from_delete} sauvé(s) du nettoyage)."
            )
            record = await self.write_memory(
                body, kind="curation-plan", tags=("curation", pole), important=False
            )
            written.append(record)
        return ScriptResult(
            status="success",
            summary=(
                f"{len(written)} pôle(s) scanné(s), {total_candidates} fait(s) safe-to-delete"
            ),
            written=written,
        )


__all__ = ["MemorySweepScript"]
