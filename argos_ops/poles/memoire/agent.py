"""``MemoireAgent`` — le cerveau du pôle Mémoire (archi v2, S7).

Agent **particulier** : déclenché PAR UN SCRIPT (``trigger: script`` dans
``pole.yaml``), **par pôle ciblé**. Il lit le pôle visé EN ENTIER, identifie le
périmé / stale, **protège tout fait ``important``** (et les patterns protégés),
et **propose** une liste « safe to delete » (:class:`CurationPlan`). Il ne
supprime **jamais** lui-même — c'est le script ``MemoryCleaner`` qui exécute la
liste validée par l'humain (« le LLM propose, Python tranche »).

Point d'extension cerveau (D-017) : :meth:`_plan` pourrait, sous
``OPS_BRAIN_ENABLED``, affiner le récit / la priorisation via ``claude -p`` —
mais le fallback heuristique :func:`plan_curation` reste la vérité, et le cerveau
ne peut **jamais** rendre supprimable un fait protégé (l'invariant vit dans la
logique pure + le double garde-fou du cleaner).
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from argos_ops.poles.agent import AgentContext, AgentResult, BaseAgent
from argos_ops.poles.config import POLES_DIR
from argos_ops.poles.memoire.curation import CurationPlan, plan_curation
from argos_ops.poles.memoire.policy import MemoryPolicy, load_policy
from argos_ops.poles.memory import MemoryRecord, read_pole_memory


class MemoireAgent(BaseAgent):
    """Propose un plan de curation pour un pôle ciblé (jamais ne supprime)."""

    pole = "memoire"
    name = "MemoireAgent"

    def __init__(
        self,
        target_pole: str,
        *,
        poles_root: Path = POLES_DIR,
        policy: MemoryPolicy | None = None,
        now: datetime | None = None,
    ) -> None:
        super().__init__(poles_root=poles_root)
        self.target_pole = target_pole
        self._policy = policy
        self._now = now

    def _plan(
        self, records_by_script: dict[str, list[MemoryRecord]], policy: MemoryPolicy
    ) -> CurationPlan:
        """Point d'extension du cerveau (D-017). Défaut = heuristique pure."""
        return plan_curation(records_by_script, policy, self.target_pole, now=self._now)

    async def build_plan(self) -> CurationPlan:
        """Lit le pôle ciblé EN ENTIER et renvoie le plan de curation proposé."""
        policy = self._policy or load_policy(poles_root=self.poles_root)
        by_script = await read_pole_memory(self.target_pole, poles_root=self.poles_root)
        return self._plan(by_script, policy)

    async def act(self, context: AgentContext) -> AgentResult:
        """Propose le plan de curation du pôle ciblé (résumé + actions = candidats)."""
        plan = await self.build_plan()
        if plan.scanned == 0:
            return AgentResult(
                status="skipped",
                summary=f"{self.target_pole} : aucune mémoire — rien à curer.",
            )
        if not plan.active:
            return AgentResult(
                status="skipped",
                summary=(
                    f"{self.target_pole} : pôle non actif (policy) — "
                    f"{plan.scanned} fait(s) intacts."
                ),
            )

        actions = [f"[{c.reason}] {c.script}/{c.record_id} — {c.detail}" for c in plan.to_delete]
        summary = (
            f"{self.target_pole} : {plan.n_delete} fait(s) safe-to-delete sur "
            f"{plan.scanned} scanné(s) — {plan.n_important} important(s) protégé(s), "
            f"{plan.n_saved_from_delete} sauvé(s) du nettoyage."
        )
        return AgentResult(status="success", summary=summary, actions=actions)


__all__ = ["MemoireAgent"]
