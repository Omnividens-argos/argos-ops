"""Synthèse du **plan d'actions** du pôle Vente (archi v2, S4) — pur, déterministe.

Brique partagée par :class:`~argos_ops.poles.vente.agent.VenteAgent` (qui agit
dessus) et l'API cockpit (qui le sert). À partir des faits mémoire du pôle (écrits
par ses 12 scripts) **plus** la mémoire cross-pôle (Veille = signaux d'achat,
Marketing = message), produit une liste d'actions priorisées par sévérité.

**Garde-fou (« Python tranche »)** : quand l'outbound est gelé (conformité
Bloctel, cf. :func:`argos_ops.poles.vente.outreach.outbound_frozen`), toute action
d'outbound est marquée ``suppressed_by_compliance`` — le plan la conserve pour
visibilité mais elle ne peut pas être exécutée. Le cerveau (``claude -p``, D-017)
peut surcharger l'ordre/les angles mais jamais lever ce gel ; le fallback
heuristique reste :func:`plan_actions`.

Aucune I/O, aucun LLM ici (testable offline).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from argos_ops.poles.memory import MemoryRecord

Severity = str  # "info" | "warning" | "critical"

_SEVERITY_RANK: dict[str, int] = {"info": 0, "warning": 1, "critical": 2}
_CRITICAL_TAG = "critical"

# Faits cross-pôle (Veille) qui mènent à de la prospection ⇒ soumis au gel Bloctel.
_BUYING_SIGNAL_KINDS: frozenset[str] = frozenset({"intent_signal", "breach", "cve", "darkweb"})
# Faits cross-pôle (Veille) réutilisables comme argument de vente (pas d'outbound).
_ARGUMENT_KINDS: frozenset[str] = frozenset({"regulatory", "competitor"})
_PREVIEW_CHARS = 130


def severity_rank(severity: str) -> int:
    return _SEVERITY_RANK.get(severity, 0)


def _record_severity(record: MemoryRecord) -> Severity:
    """Sévérité d'un fait : tag ``critical`` > flag ``important`` > info."""
    if _CRITICAL_TAG in record.tags:
        return "critical"
    if record.important:
        return "warning"
    return "info"


@dataclass(frozen=True)
class VentePlan:
    """Une action commerciale / relation client planifiée."""

    severity: Severity
    kind: str  # ticket | account | inbound | outreach | argument | upsell | meeting
    action: str
    detail: str
    suppressed_by_compliance: bool = False
    record_ids: tuple[str, ...] = field(default_factory=tuple)


def _route(record: MemoryRecord, *, outbound_frozen: bool) -> VentePlan | None:
    """Mappe un fait mémoire vers une action de plan. ``None`` = non actionnable."""
    tags = set(record.tags)
    detail = record.body[:_PREVIEW_CHARS]
    sev = _record_severity(record)

    if record.kind == "ticket":
        if "P0" in tags or "breach" in tags:
            severity, label = "critical", "Traiter le ticket support (P0 / SLA dépassé)"
        elif "P1" in tags:
            severity, label = "warning", "Traiter le ticket support (P1)"
        else:
            severity, label = "info", "Traiter le ticket support (P2)"
        return VentePlan(severity, "ticket", label, detail, record_ids=(record.id,))

    if record.kind == "health" and "red" in tags:
        return VentePlan(
            "critical",
            "account",
            "Appeler le compte (santé rouge)",
            detail,
            record_ids=(record.id,),
        )

    if record.kind == "churn":
        severity = "critical" if record.important else "warning"
        return VentePlan(
            severity,
            "account",
            "Plan de rétention (signaux pré-churn)",
            detail,
            record_ids=(record.id,),
        )

    if record.kind == "inbound":
        if "human_requested" in tags:
            return VentePlan(
                "critical",
                "inbound",
                "Réponse HUMAINE requise (AI Act)",
                detail,
                record_ids=(record.id,),
            )
        if "lead_chaud" in tags:
            return VentePlan(
                "warning",
                "inbound",
                "Qualifier / répondre au lead chaud",
                detail,
                record_ids=(record.id,),
            )
        if "sav" in tags:
            return VentePlan(
                "warning", "inbound", "Traiter la demande SAV", detail, record_ids=(record.id,)
            )
        return None

    if record.kind == "lead" and record.important:  # lead qualifié (BANT ≥ 40)
        return VentePlan(
            "warning",
            "outreach",
            "Lancer une séquence outbound (lead qualifié)",
            detail,
            suppressed_by_compliance=outbound_frozen,
            record_ids=(record.id,),
        )

    if record.kind in _BUYING_SIGNAL_KINDS:
        severity = sev if sev != "info" else "warning"
        return VentePlan(
            severity,
            "outreach",
            "Prospecter (signal d'achat Veille)",
            detail,
            suppressed_by_compliance=outbound_frozen,
            record_ids=(record.id,),
        )

    if record.kind in _ARGUMENT_KINDS:
        return VentePlan(
            "info",
            "argument",
            "Réutiliser comme argument de vente (Veille)",
            detail,
            record_ids=(record.id,),
        )

    if record.kind == "upsell":
        return VentePlan(
            "info", "upsell", "Proposer un upsell (compte saturé)", detail, record_ids=(record.id,)
        )

    if record.kind == "meeting":
        return VentePlan(
            "info",
            "meeting",
            "Envoyer la confirmation de RDV (iCal drafté)",
            detail,
            record_ids=(record.id,),
        )

    return None


def plan_actions(records: list[MemoryRecord], *, outbound_frozen: bool) -> list[VentePlan]:
    """Synthétise un plan d'actions priorisé depuis les faits visibles.

    Tri : sévérité décroissante, puis actions exécutables avant les gelées
    (compliance), puis par type. Stable et déterministe.
    """
    plans = [p for r in records if (p := _route(r, outbound_frozen=outbound_frozen)) is not None]
    plans.sort(
        key=lambda p: (severity_rank(p.severity), not p.suppressed_by_compliance, p.kind),
        reverse=True,
    )
    return plans


__all__ = ["Severity", "VentePlan", "plan_actions", "severity_rank"]
