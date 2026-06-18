"""Synthèse éditoriale du pôle Marketing (archi v2, S2).

Brique *pure et déterministe* — l'analogue marketing de
:mod:`argos_ops.poles.veille.insights`. Elle transforme les **signaux de veille**
(lus en cross-pôle) en **recommandations de contenu** routées par canal : quel
sujet pousser, sur quels réseaux, avec quel angle. Partagée par :

- :class:`~argos_ops.poles.marketing.agent.MarketingAgent` (qui agit dessus) ;
- l'endpoint cockpit ``GET /api/poles/marketing/overview`` (qui les sert au front).

Le marketing est **en aval** de la veille : il ne décide pas du terrain, il le
met en récit. La table de routage ``kind de signal → (angle, canaux)`` encode la
ligne éditoriale Argos. Garde-fou **anti-FUD** (cf. CLAUDE.md / charte) : les
familles « menace » (breach / CVE / dark web) sont routées vers un angle
**pédagogique et défensif**, jamais anxiogène.

Aucune I/O, aucune API tierce, aucun LLM ici (D-017) : un agent peut brancher le
cerveau (``claude -p``) par-dessus, mais le fallback heuristique reste cette
fonction, et c'est elle que les tests vérifient.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from argos_ops.poles.marketing.channels import CHANNEL_IDS
from argos_ops.poles.memory import MemoryRecord

# =============================================================================
# Sévérité — même échelle ordinale que la veille (info < warning < critical)
# =============================================================================
Severity = str  # "info" | "warning" | "critical"

_SEVERITY_RANK: dict[str, int] = {"info": 0, "warning": 1, "critical": 2}
_CRITICAL_TAG = "critical"


def severity_rank(severity: str) -> int:
    return _SEVERITY_RANK.get(severity, 0)


def record_severity(record: MemoryRecord) -> Severity:
    """Sévérité d'un fait : tag ``critical`` > flag ``important`` > info."""
    if _CRITICAL_TAG in record.tags:
        return "critical"
    if record.important:
        return "warning"
    return "info"


# =============================================================================
# Table de routage éditorial : kind de signal de veille → (angle, canaux)
# =============================================================================
# L'ordre des canaux = priorité décroissante de pertinence. ``intent_signal``
# est absent volontairement : c'est un signal d'achat (pôle Vente), pas un sujet
# de contenu. Les familles « menace » pointent vers un angle pédagogique
# (anti-FUD), jamais alarmiste.
_KIND_ROUTING: dict[str, tuple[str, tuple[str, ...]]] = {
    "trend": ("Décryptage pédagogique du sujet chaud", ("linkedin", "x", "blog", "mastodon")),
    "competitor": ("Différenciation Argos, sans dénigrer", ("linkedin", "blog")),
    "regulatory": (
        "Mise en conformité expliquée simplement",
        ("linkedin", "newsletter", "blog"),
    ),
    "breach": ("Retour d'expérience défensif (zéro FUD)", ("linkedin", "x", "mastodon")),
    "cve": ("Vulgarisation + réflexe de remédiation", ("x", "linkedin", "mastodon")),
    "darkweb": ("Sensibilisation exposition de données (factuel)", ("linkedin", "meta")),
    "press": ("Amplification de la mention presse", ("linkedin", "meta")),
    "seo_movement": ("Renforcer le contenu sur le mot-clé", ("blog",)),
}

ROUTABLE_KINDS: frozenset[str] = frozenset(_KIND_ROUTING)

_TOPIC_PREVIEW_CHARS = 110
_SUMMARY_MAX_ITEMS = 3


@dataclass(frozen=True)
class Recommendation:
    """Une recommandation de contenu issue d'un groupe de signaux de veille.

    Une recommandation = une famille de signaux (``kind``) à mettre en récit,
    qualifiée par sa sévérité maximale et routée vers les canaux pertinents.
    """

    kind: str
    topic: str
    angle: str
    severity: Severity
    channels: tuple[str, ...]
    rationale: str
    record_ids: tuple[str, ...] = field(default_factory=tuple)
    count: int = 0


def routing_for(kind: str) -> tuple[str, tuple[str, ...]] | None:
    """(angle, canaux) pour un ``kind`` routable, ou ``None`` si non éditorial."""
    return _KIND_ROUTING.get(kind)


def plan_editorial(records: list[MemoryRecord]) -> list[Recommendation]:
    """Agrège les signaux *routables* en recommandations, du plus grave au moins.

    - Une recommandation par ``kind`` éditorial présent dans les faits.
    - Sévérité = sévérité max du groupe.
    - ``topic`` = aperçu du signal le plus grave / récent du groupe.
    - Tri stable : sévérité décroissante, puis cardinalité décroissante.

    Les faits non routables (mémoire propre du marketing : publications,
    engagement, médias ; ou ``intent_signal`` de la veille) sont ignorés.
    """
    by_kind: dict[str, list[MemoryRecord]] = defaultdict(list)
    for record in records:
        if record.kind in _KIND_ROUTING:
            by_kind[record.kind].append(record)

    recommendations: list[Recommendation] = []
    for kind, group in by_kind.items():
        angle, channels = _KIND_ROUTING[kind]
        # On ne route que vers des canaux connus (défensif si la table évolue).
        channels = tuple(c for c in channels if c in CHANNEL_IDS)
        ranked = sorted(
            group,
            key=lambda r: (severity_rank(record_severity(r)), r.created_at),
            reverse=True,
        )
        group_severity = record_severity(ranked[0]) if ranked else "info"
        topic = ranked[0].body[:_TOPIC_PREVIEW_CHARS] if ranked else kind
        preview = " · ".join(r.body[:_TOPIC_PREVIEW_CHARS] for r in ranked[:_SUMMARY_MAX_ITEMS])
        recommendations.append(
            Recommendation(
                kind=kind,
                topic=topic,
                angle=angle,
                severity=group_severity,
                channels=channels,
                rationale=f"{len(group)} signal(aux) « {kind} » à valoriser — {preview}",
                record_ids=tuple(r.id for r in ranked),
                count=len(group),
            )
        )

    recommendations.sort(key=lambda r: (severity_rank(r.severity), r.count), reverse=True)
    return recommendations


__all__ = [
    "ROUTABLE_KINDS",
    "Recommendation",
    "Severity",
    "plan_editorial",
    "record_severity",
    "routing_for",
    "severity_rank",
]
