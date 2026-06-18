"""Synthèse des signaux de veille en **insights actionnables** (archi v2, S1).

Brique *pure et déterministe* partagée par :

- :class:`~argos_ops.poles.veille.agent.VeilleAgent` (le cerveau du pôle, qui
  agit dessus) ;
- l'endpoint cockpit ``GET /api/poles/veille/feed`` (qui les sert au front).

Le pôle Veille est **en amont** : il ne décide rien côté business, il *qualifie*
et *route*. Chaque famille de signal écrite par un script (``kind``) est mappée
vers un thème lisible et la liste des pôles aval qui devraient s'en saisir
(Marketing / Pub / Vente). C'est cette table de routage qui alimente le bouton
« pousser vers … » du cockpit — sans jamais écrire dans un autre pôle (la
décision reste humaine et le câblage cross-pôle viendra plus tard).

Aucune I/O, aucune API tierce, aucun LLM ici (D-017) : un agent peut brancher le
cerveau (``claude -p``) par-dessus, mais le fallback heuristique reste cette
fonction, et c'est elle que les tests vérifient.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from argos_ops.poles.memory import MemoryRecord

# =============================================================================
# Sévérité — échelle ordinale partagée (info < warning < critical)
# =============================================================================
Severity = str  # "info" | "warning" | "critical"

_SEVERITY_RANK: dict[str, int] = {"info": 0, "warning": 1, "critical": 2}
_CRITICAL_TAG = "critical"


def severity_rank(severity: str) -> int:
    """Rang ordinal d'une sévérité (inconnue ⇒ 0)."""
    return _SEVERITY_RANK.get(severity, 0)


def record_severity(record: MemoryRecord) -> Severity:
    """Sévérité d'un fait : tag ``critical`` > flag ``important`` > info."""
    if _CRITICAL_TAG in record.tags:
        return "critical"
    if record.important:
        return "warning"
    return "info"


# =============================================================================
# Table de routage : kind de signal → (thème lisible, pôles aval suggérés)
# =============================================================================
# Veille est en amont : elle ne fait que *suggérer* quel pôle devrait se saisir
# d'un signal. L'ordre des pôles = priorité décroissante de pertinence.
DOWNSTREAM_POLES: tuple[str, ...] = ("marketing", "pub", "vente")

_KIND_ROUTING: dict[str, tuple[str, tuple[str, ...]]] = {
    "trend": ("marché", ("marketing", "pub")),
    "competitor": ("concurrence", ("marketing", "pub", "vente")),
    "regulatory": ("réglementaire", ("marketing", "vente")),
    "breach": ("menace", ("vente",)),
    "cve": ("menace", ("vente",)),
    "darkweb": ("menace", ("vente",)),
    "press": ("réputation", ("marketing",)),
    "seo_movement": ("seo", ("marketing", "pub")),
    "intent_signal": ("intention d'achat", ("vente",)),
}
_DEFAULT_ROUTING: tuple[str, tuple[str, ...]] = ("autre", ())

_SUMMARY_PREVIEW_CHARS = 90
_SUMMARY_MAX_ITEMS = 3


@dataclass(frozen=True)
class Insight:
    """Un insight de veille synthétisé à partir d'un groupe de signaux.

    Un insight = une famille de signaux (``kind``) agrégée, qualifiée par sa
    sévérité maximale et routée vers les pôles aval qui devraient s'en saisir.
    """

    kind: str
    title: str
    theme: str
    severity: Severity
    summary: str
    suggested_poles: tuple[str, ...]
    record_ids: tuple[str, ...] = field(default_factory=tuple)
    count: int = 0


def routing_for(kind: str) -> tuple[str, tuple[str, ...]]:
    """(thème, pôles aval) pour un ``kind`` de signal. Inconnu ⇒ ("autre", ())."""
    return _KIND_ROUTING.get(kind, _DEFAULT_ROUTING)


def synthesize_insights(records: list[MemoryRecord]) -> list[Insight]:
    """Agrège les faits de veille en insights, triés du plus grave au moins grave.

    - Un insight par ``kind`` présent dans les faits.
    - Sévérité de l'insight = sévérité max de son groupe.
    - ``summary`` = aperçu des faits les plus graves / récents du groupe.
    - Tri stable : sévérité décroissante, puis cardinalité décroissante.
    """
    by_kind: dict[str, list[MemoryRecord]] = defaultdict(list)
    for record in records:
        by_kind[record.kind].append(record)

    insights: list[Insight] = []
    for kind, group in by_kind.items():
        theme, poles = routing_for(kind)
        ranked = sorted(
            group,
            key=lambda r: (severity_rank(record_severity(r)), r.created_at),
            reverse=True,
        )
        group_severity = record_severity(ranked[0]) if ranked else "info"
        preview = " · ".join(r.body[:_SUMMARY_PREVIEW_CHARS] for r in ranked[:_SUMMARY_MAX_ITEMS])
        insights.append(
            Insight(
                kind=kind,
                title=f"{len(group)} signal(aux) « {kind} » ({theme})",
                theme=theme,
                severity=group_severity,
                summary=preview,
                suggested_poles=poles,
                record_ids=tuple(r.id for r in ranked),
                count=len(group),
            )
        )

    insights.sort(key=lambda i: (severity_rank(i.severity), i.count), reverse=True)
    return insights


__all__ = [
    "DOWNSTREAM_POLES",
    "Insight",
    "Severity",
    "record_severity",
    "routing_for",
    "severity_rank",
    "synthesize_insights",
]
