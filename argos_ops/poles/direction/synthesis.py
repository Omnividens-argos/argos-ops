"""Synthèse de la semaine — pôle Direction (archi v2, S6).

La « synthèse IA de la semaine » du cockpit. Sous D-017, c'est le cerveau
(``claude -p``) qui *rédigerait* idéalement ce récit ; ce module en fournit le
**fallback heuristique déterministe** (obligatoire : un agent ne crashe jamais
cerveau OFF) à partir de la vue d'ensemble (:class:`FleetSnapshot`), du rapport
OKR (:class:`OKRReport`) et du garde-fou de publication (:class:`ReleaseGate`).

Le ``DirectionAgent`` expose un point d'extension :meth:`_synthesize` dont le
défaut est :func:`build_synthesis`. Aucune I/O, aucun LLM ici (testable offline).
"""

from __future__ import annotations

from dataclasses import dataclass

from argos_ops.agents.okr_tracker import OKRReport
from argos_ops.poles.direction.fleet import FleetSnapshot
from argos_ops.poles.direction.release import ReleaseGate


@dataclass(frozen=True)
class SynthesisReport:
    """Récit de pilotage de la semaine (déterministe)."""

    headline: str
    narrative: str
    highlights: tuple[str, ...]
    risks: tuple[str, ...]


def build_synthesis(snapshot: FleetSnapshot, okr: OKRReport, gate: ReleaseGate) -> SynthesisReport:
    """Compose un récit court : état global, points saillants, risques."""
    if snapshot.poles_red:
        headline = (
            f"⚠️ {snapshot.poles_red} pôle(s) en alerte critique — pilotage en mode vigilance."
        )
    elif snapshot.poles_yellow:
        headline = f"{snapshot.poles_yellow} pôle(s) à surveiller — flotte globalement saine."
    elif snapshot.poles_active:
        headline = "Flotte saine — tous les pôles actifs au vert."
    else:
        headline = "Flotte au repos — aucune activité mémoire récente."

    highlights: list[str] = []
    healthy = [p for p in snapshot.poles if p.health == "healthy"]
    if healthy:
        highlights.append(f"{len(healthy)} pôle(s) au vert : {', '.join(p.name for p in healthy)}.")
    completed = [k for k in okr.key_results if k.status == "completed"]
    if completed:
        highlights.append(f"{len(completed)} OKR atteint(s) ce trimestre ({okr.quarter}).")
    on_track = [k for k in okr.key_results if k.status == "on_track"]
    if on_track:
        highlights.append(f"{len(on_track)} OKR on-track vs prorata temporis.")

    risks: list[str] = []
    for p in snapshot.red_poles:
        risks.append(f"{p.name} : {p.headline or 'signal critique'}.")
    off_track = [k for k in okr.key_results if k.status == "off_track"]
    for k in off_track[:3]:
        risks.append(
            f"OKR « {k.name} » off-track ({k.progress_pct * 100:.0f}% vs {k.expected_pct * 100:.0f}% attendu)."
        )
    if gate.blocking:
        risks.append(f"Publication GELÉE — {gate.reason}.")

    narrative_parts = [headline]
    narrative_parts.append(
        f"État flotte : {snapshot.poles_active}/{len(snapshot.poles)} pôle(s) actif(s), "
        f"{snapshot.total_facts} fait(s) en mémoire, {snapshot.total_critical} signal(aux) critique(s). "
        f"OKR {okr.quarter} — {okr.summary}."
    )
    if risks:
        narrative_parts.append("Risques : " + " ".join(risks))
    if highlights:
        narrative_parts.append("Points positifs : " + " ".join(highlights))

    return SynthesisReport(
        headline=headline,
        narrative=" ".join(narrative_parts),
        highlights=tuple(highlights),
        risks=tuple(risks),
    )


__all__ = ["SynthesisReport", "build_synthesis"]
