"""Synthèse du plan d'actions du pôle Pub (archi v2, S3).

Brique *pure et déterministe* — l'analogue Pub de
:mod:`argos_ops.poles.marketing.editorial`. Elle transforme ce que voit l'agent
(mémoire propre + Veille/Marketing/Finance en cross-pôle) en un **plan d'actions**
de deux familles :

- ``creative_idea`` : un signal de **Veille** (tendance / CVE / breach / …) à
  transformer en campagne, routé vers des plateformes pertinentes. Garde-fou
  **anti-FUD** : les familles « menace » sont routées vers un angle défensif
  pédagogique, jamais anxiogène.
- ``budget_action`` : une reco chiffrée écrite par le script ``ads_optimizer``
  (fait ``kind="ad_reco"``), dont l'action est lue dans les tags.

**Garde-fou central « Python tranche »** : si le breaker ``ad_spend_runaway`` est
armé, toute action *augmentatrice de dépense* (``scale`` / ``new_creative``) est
marquée ``suppressed_by_breaker`` — le plan la conserve pour audit mais la signale
bloquée. Le cerveau (``claude -p``) peut surcharger l'angle, jamais lever ce gel.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from argos_ops.poles.memory import MemoryRecord
from argos_ops.poles.pub.optimizer import SPEND_INCREASING, severity_rank
from argos_ops.poles.pub.platforms import PLATFORM_IDS

Severity = str  # "info" | "warning" | "critical"
_CRITICAL_TAG = "critical"

AD_RECO_KIND = "ad_reco"
_KNOWN_ACTIONS: frozenset[str] = frozenset(
    {"pause", "drop_keyword", "new_creative", "diagnose_lp", "scale"}
)

# Routage d'une idée de créa : kind de signal Veille → (angle, plateformes).
# Les menaces (breach / cve / darkweb) pointent vers un angle défensif (anti-FUD).
# Absents volontairement : ``intent_signal`` (Vente), ``seo_movement`` (organique),
# ``press`` (RP) — pas du ressort de l'acquisition payante.
_IDEA_ROUTING: dict[str, tuple[str, tuple[str, ...]]] = {
    "trend": ("Capitaliser sur le sujet chaud", ("google_search", "linkedin_sponsored")),
    "cve": ("Réflexe de remédiation (pédagogique)", ("google_search",)),
    "breach": ("Réassurance défensive, zéro FUD", ("linkedin_sponsored",)),
    "competitor": ("Différenciation Argos, sans dénigrer", ("linkedin_sponsored", "google_search")),
    "regulatory": ("Mise en conformité expliquée", ("linkedin_sponsored", "google_search")),
    "darkweb": ("Sensibilisation exposition de données (factuel)", ("meta", "linkedin_sponsored")),
}

IDEA_KINDS: frozenset[str] = frozenset(_IDEA_ROUTING)
_TOPIC_PREVIEW_CHARS = 110


@dataclass(frozen=True)
class AdPlan:
    """Une entrée du plan d'actions du pôle Pub."""

    kind: str  # "creative_idea" | "budget_action"
    action: str  # "new_campaign" (idea) | pause/scale/drop_keyword/… (budget)
    platforms: tuple[str, ...]
    angle: str
    severity: Severity
    rationale: str
    record_ids: tuple[str, ...] = field(default_factory=tuple)
    suppressed_by_breaker: bool = False


def record_severity(record: MemoryRecord) -> Severity:
    """Sévérité d'un fait : tag ``critical`` > flag ``important`` > info."""
    if _CRITICAL_TAG in record.tags:
        return "critical"
    if record.important:
        return "warning"
    return "info"


def _action_of(record: MemoryRecord) -> str | None:
    """Lit l'action d'une reco budget dans ses tags (1er tag d'action connue)."""
    for tag in record.tags:
        if tag in _KNOWN_ACTIONS:
            return tag
    return None


def _plan_creative_ideas(records: list[MemoryRecord]) -> list[AdPlan]:
    """Agrège les signaux Veille routables en idées de campagne (1 par kind)."""
    by_kind: dict[str, list[MemoryRecord]] = defaultdict(list)
    for record in records:
        if record.kind in _IDEA_ROUTING:
            by_kind[record.kind].append(record)

    plans: list[AdPlan] = []
    for kind, group in by_kind.items():
        angle, platforms = _IDEA_ROUTING[kind]
        platforms = tuple(p for p in platforms if p in PLATFORM_IDS)
        ranked = sorted(
            group,
            key=lambda r: (severity_rank(record_severity(r)), r.created_at),
            reverse=True,
        )
        group_sev = record_severity(ranked[0])
        preview = ranked[0].body[:_TOPIC_PREVIEW_CHARS]
        plans.append(
            AdPlan(
                kind="creative_idea",
                action="new_campaign",
                platforms=platforms,
                angle=angle,
                severity=group_sev,
                rationale=f"{len(group)} signal(aux) « {kind} » à transformer en créa — {preview}",
                record_ids=tuple(r.id for r in ranked),
            )
        )
    return plans


def _plan_budget_actions(records: list[MemoryRecord], *, breaker_tripped: bool) -> list[AdPlan]:
    """Transforme les recos ``ad_reco`` en actions budget, gelées si breaker armé."""
    plans: list[AdPlan] = []
    for record in records:
        if record.kind != AD_RECO_KIND:
            continue
        action = _action_of(record)
        if action is None:
            continue
        platform = next((t for t in record.tags if t in PLATFORM_IDS), None)
        suppressed = breaker_tripped and action in SPEND_INCREASING
        plans.append(
            AdPlan(
                kind="budget_action",
                action=action,
                platforms=(platform,) if platform else (),
                angle=record.body[:_TOPIC_PREVIEW_CHARS],
                severity=record_severity(record),
                rationale=record.body[:_TOPIC_PREVIEW_CHARS],
                record_ids=(record.id,),
                suppressed_by_breaker=suppressed,
            )
        )
    return plans


def plan_actions(records: list[MemoryRecord], *, breaker_tripped: bool = False) -> list[AdPlan]:
    """Synthétise le plan d'actions du pôle Pub, du plus grave au moins grave.

    - Actions budget (recos ``ad_reco``) + idées de créa (signaux Veille routables).
    - Si ``breaker_tripped`` : les actions ``scale`` / ``new_creative`` sont
      conservées mais marquées ``suppressed_by_breaker`` (gel « Python tranche »).
    - Tri stable : sévérité décroissante ; à sévérité égale, les actions budget
      passent avant les idées (plus urgentes), et les actions gelées en dernier.
    """
    plans = _plan_budget_actions(records, breaker_tripped=breaker_tripped)
    plans += _plan_creative_ideas(records)

    def sort_key(p: AdPlan) -> tuple[int, int, int]:
        kind_rank = 1 if p.kind == "budget_action" else 0
        return (severity_rank(p.severity), kind_rank, 0 if not p.suppressed_by_breaker else -1)

    plans.sort(key=sort_key, reverse=True)
    return plans


__all__ = [
    "AD_RECO_KIND",
    "IDEA_KINDS",
    "AdPlan",
    "Severity",
    "plan_actions",
    "record_severity",
]
