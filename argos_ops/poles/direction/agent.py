"""``DirectionAgent`` — le cerveau du pôle Direction (archi v2, S6).

Le pôle Direction est **transversal** : il lit sa propre mémoire (faits écrits par
ses 9 scripts : digests, OKR, board, décisions, changelog, roadmap, feedback, bugs)
**plus** la mémoire de **toute la flotte** en cross-pôle (``reads_cross_pole: ["*"]``
dans ``pole.yaml``), puis **synthétise** deux choses : un *récit de la semaine*
(:func:`~argos_ops.poles.direction.synthesis.build_synthesis`) et un *plan
d'oversight priorisé* (:func:`~argos_ops.poles.direction.plan.plan_actions`).

**Garde-fou central** : avant de planifier, l'agent évalue le garde-fou de
publication (:func:`~argos_ops.poles.direction.release.evaluate` — bug P0 ouvert ou
pôle critique) et **gèle** toute action de publication d'artefact public (release
notes / changelog / roadmap) s'il est armé. « Le LLM propose, Python tranche » :
sous D-017 le cerveau réel (``claude -p``) surchargerait :meth:`_plan` /
:meth:`_synthesize` pour affiner priorités et récit, mais ne peut jamais lever ce
gel. Les fallbacks heuristiques restent :func:`plan_actions` / :func:`build_synthesis`.
Strict miroir du gel Bloctel de la Vente / de la conformité de la Finance.
"""

from __future__ import annotations

from argos_ops.poles.agent import AgentContext, AgentResult, BaseAgent
from argos_ops.poles.direction import bugs, okr, release
from argos_ops.poles.direction.fleet import FleetSnapshot, build_fleet_snapshot
from argos_ops.poles.direction.plan import DirectionPlan, plan_actions
from argos_ops.poles.direction.release import ReleaseGate
from argos_ops.poles.direction.synthesis import SynthesisReport, build_synthesis
from argos_ops.poles.memory import MemoryRecord


class DirectionAgent(BaseAgent):
    """Synthétise la flotte entière en récit + plan d'oversight borné par le gel publication."""

    pole = "direction"
    name = "DirectionAgent"

    def _plan(self, records: list[MemoryRecord], *, release_blocking: bool) -> list[DirectionPlan]:
        """Point d'extension du cerveau (D-017). Défaut = heuristique pure."""
        return plan_actions(records, release_blocking=release_blocking)

    def _synthesize(
        self, snapshot: FleetSnapshot, okr_report: okr.OKRReport, gate: ReleaseGate
    ) -> SynthesisReport:
        """Point d'extension du cerveau (D-017). Défaut = récit heuristique."""
        return build_synthesis(snapshot, okr_report, gate)

    async def act(self, context: AgentContext) -> AgentResult:
        # Garde-fou Python : le gel publication borne le plan AVANT toute décision.
        snapshot = await build_fleet_snapshot(poles_root=self.poles_root)
        gate = release.evaluate(snapshot, bugs.open_p0(poles_root=self.poles_root))
        records = context.all_records()
        if not records:
            return AgentResult(
                status="skipped",
                summary="Aucune mémoire (propre ni cross-pôle) — rien à piloter.",
            )

        okr_report = okr.load_current(poles_root=self.poles_root)
        synth = self._synthesize(snapshot, okr_report, gate)
        plans = self._plan(records, release_blocking=gate.blocking)

        actions = [
            f"[{p.severity}] {p.action} ({p.kind})"
            f"{' [GELÉ publication]' if p.suppressed_by_release else ''}"
            for p in plans
        ]
        suppressed = sum(1 for p in plans if p.suppressed_by_release)
        critical = sum(1 for p in plans if p.severity == "critical")
        cross_seen = sorted(context.cross_pole.keys())
        cross_note = f" (cross-pôle : {', '.join(cross_seen)})" if cross_seen else ""
        gel_note = (
            f" — publication GELÉE ({gate.reason}), {suppressed} action(s) suspendue(s)"
            if gate.blocking and suppressed
            else ""
        )
        summary = (
            f"{synth.headline} {len(plans)} action(s) d'oversight depuis {len(records)} fait(s)"
            f"{cross_note} — {critical} critique(s){gel_note}"
        )
        return AgentResult(status="success", summary=summary, actions=actions)


__all__ = ["DirectionAgent"]
