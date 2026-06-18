"""Synthèse du **plan d'oversight** du pôle Direction (archi v2, S6) — pur.

Brique partagée par le :class:`~argos_ops.poles.direction.agent.DirectionAgent`
(qui agit dessus) et l'API cockpit (qui le sert). À partir des faits mémoire du
pôle (écrits par ses 9 scripts) **plus** la mémoire cross-pôle de **toute** la
flotte, produit une liste d'actions de pilotage priorisées par sévérité :
arbitrage de bugs, redressement d'OKR, arbitrage produit, diffusion des décisions,
**publication** d'artefacts, et **supervision** des pôles en alerte.

**Garde-fou (« Python tranche »)** : quand la publication est gelée
(:func:`argos_ops.poles.direction.release.release_blocking` — bug P0 ouvert ou
pôle critique), toute action de **publication** (release notes / changelog /
roadmap) est marquée ``suppressed_by_release`` — conservée pour visibilité mais
non exécutable. Le cerveau (``claude -p``, D-017) peut réordonner mais jamais
lever ce gel. Strict miroir du gel Bloctel de la Vente.

Aucune I/O, aucun LLM ici (testable offline).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from argos_ops.poles.direction.fleet import DIRECTION_POLE, fact_severity
from argos_ops.poles.memory import MemoryRecord

Severity = str  # "info" | "warning" | "critical"

_SEVERITY_RANK: dict[str, int] = {"info": 0, "warning": 1, "critical": 2}
_PREVIEW_CHARS = 140

# Artefacts publics dont la publication est soumise au garde-fou release. Source
# canonique unique réutilisée par l'API cockpit (``api/direction.py``) pour le 409
# de génération — les tokens du plan et de la génération de doc restent alignés.
PUBLISHABLE_KINDS: frozenset[str] = frozenset({"changelog", "roadmap", "release_notes"})


def severity_rank(severity: str) -> int:
    return _SEVERITY_RANK.get(severity, 0)


@dataclass(frozen=True)
class DirectionPlan:
    """Une action de pilotage planifiée par la Direction."""

    severity: Severity
    kind: str  # bug|okr|feedback|decision|publish|board|oversight
    action: str
    detail: str
    pole: str  # le pôle concerné (direction ou un pôle supervisé)
    suppressed_by_release: bool = False
    record_ids: tuple[str, ...] = field(default_factory=tuple)


def _has(record: MemoryRecord, *tags: str) -> bool:
    s = {t.lower() for t in record.tags}
    return any(t in s for t in tags)


def _route_own(record: MemoryRecord, *, release_blocking: bool) -> DirectionPlan | None:
    """Mappe un fait du pôle Direction vers une action. ``None`` = non actionnable."""
    detail = record.body[:_PREVIEW_CHARS]
    ids = (record.id,)
    kind = record.kind

    if kind == "bug":
        if _has(record, "p0"):
            sev = "critical"
        elif _has(record, "p1"):
            sev = "warning"
        else:
            sev = "info"
        return DirectionPlan(
            sev, "bug", "Arbitrer / assigner le bug", detail, DIRECTION_POLE, record_ids=ids
        )

    if kind == "okr":
        if _has(record, "off_track"):
            sev = "critical"
        elif _has(record, "at_risk"):
            sev = "warning"
        else:
            return None
        return DirectionPlan(
            sev, "okr", "Redresser l'OKR en retard", detail, DIRECTION_POLE, record_ids=ids
        )

    if kind == "feedback":
        sev = "warning" if record.important else "info"
        return DirectionPlan(
            sev,
            "feedback",
            "Arbitrer la demande produit récurrente",
            detail,
            DIRECTION_POLE,
            record_ids=ids,
        )

    if kind == "decision":
        return DirectionPlan(
            "info",
            "decision",
            "Diffuser la décision structurante",
            detail,
            DIRECTION_POLE,
            record_ids=ids,
        )

    if kind == "board":
        return DirectionPlan(
            "info", "board", "Diffuser le board pack", detail, DIRECTION_POLE, record_ids=ids
        )

    if kind in PUBLISHABLE_KINDS:
        return DirectionPlan(
            "info",
            "publish",
            f"Publier l'artefact ({kind})",
            detail,
            DIRECTION_POLE,
            suppressed_by_release=release_blocking,
            record_ids=ids,
        )

    # strategy / digest = synthèses, pas des actions.
    return None


def _oversight(pole: str, records: list[MemoryRecord]) -> DirectionPlan | None:
    """Une action de supervision par pôle cross, à sa pire sévérité (≥ warning)."""
    severities = [fact_severity(r) for r in records]
    if "critical" in severities:
        worst, sev = "critical", "critical"
    elif "warning" in severities:
        worst, sev = "warning", "warning"
    else:
        return None
    flagged = [r for r, s in zip(records, severities, strict=True) if s == worst]
    flagged.sort(key=lambda r: r.created_at, reverse=True)
    detail = flagged[0].body[:_PREVIEW_CHARS]
    action = (
        f"Superviser le pôle « {pole} » (signal critique)"
        if sev == "critical"
        else f"Surveiller le pôle « {pole} » (alerte)"
    )
    return DirectionPlan(
        sev, "oversight", action, detail, pole, record_ids=tuple(r.id for r in flagged[:5])
    )


def plan_actions(records: list[MemoryRecord], *, release_blocking: bool) -> list[DirectionPlan]:
    """Synthétise un plan d'oversight priorisé depuis les faits visibles.

    Tri : sévérité décroissante, puis actions exécutables avant les gelées (release),
    puis par type. Stable et déterministe.
    """
    plans: list[DirectionPlan] = []
    cross: dict[str, list[MemoryRecord]] = {}
    for r in records:
        if r.pole == DIRECTION_POLE:
            plan = _route_own(r, release_blocking=release_blocking)
            if plan is not None:
                plans.append(plan)
        else:
            cross.setdefault(r.pole, []).append(r)

    for pole, recs in cross.items():
        plan = _oversight(pole, recs)
        if plan is not None:
            plans.append(plan)

    plans.sort(
        key=lambda p: (severity_rank(p.severity), not p.suppressed_by_release, p.kind),
        reverse=True,
    )
    return plans


__all__ = ["PUBLISHABLE_KINDS", "DirectionPlan", "Severity", "plan_actions", "severity_rank"]
