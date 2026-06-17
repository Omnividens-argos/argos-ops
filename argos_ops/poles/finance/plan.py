"""Synthèse du **plan d'actions** du pôle Finance (archi v2, S5) — pur, déterministe.

Brique partagée par :class:`~argos_ops.poles.finance.agent.FinanceAgent` (qui agit
dessus) et l'API cockpit (qui le sert). À partir des faits mémoire du pôle (écrits
par ses 11 scripts : MRR, dunning, treasury, fiscal, RGPD, AI Act, contrats,
dépenses, rapprochement, incidents) **plus** la mémoire cross-pôle de la Vente
(devis envoyé → facture à émettre), produit une liste d'actions priorisées par
sévérité.

**Garde-fou (« Python tranche »)** : quand la conformité est bloquante
(:func:`argos_ops.poles.finance.compliance.compliance_blocking` — gap RGPD ou
système IA ``prohibited``), toute action d'**onboarding d'un nouveau traitement**
(facturer un nouveau client) est marquée ``suppressed_by_compliance`` — le plan la
conserve pour visibilité mais elle ne peut pas être exécutée. Le cerveau
(``claude -p``, D-017) peut surcharger l'ordre/le ton mais jamais lever ce gel ;
le fallback heuristique reste :func:`plan_actions`. C'est le strict miroir du gel
Bloctel de la Vente.

Aucune I/O, aucun LLM ici (testable offline).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from argos_ops.poles.memory import MemoryRecord

Severity = str  # "info" | "warning" | "critical"

_SEVERITY_RANK: dict[str, int] = {"info": 0, "warning": 1, "critical": 2}
_PREVIEW_CHARS = 140


def severity_rank(severity: str) -> int:
    return _SEVERITY_RANK.get(severity, 0)


@dataclass(frozen=True)
class FinancePlan:
    """Une action finance / conformité planifiée."""

    severity: Severity
    kind: str  # dunning|treasury|fiscal|rgpd|ai_act|contract|expense|reconcile|incident|billing_new
    action: str
    detail: str
    suppressed_by_compliance: bool = False
    record_ids: tuple[str, ...] = field(default_factory=tuple)


def _has(record: MemoryRecord, *tags: str) -> bool:
    s = set(record.tags)
    return any(t in s for t in tags)


def _route(record: MemoryRecord, *, compliance_blocking: bool) -> FinancePlan | None:
    """Mappe un fait mémoire vers une action de plan. ``None`` = non actionnable."""
    detail = record.body[:_PREVIEW_CHARS]
    ids = (record.id,)
    kind = record.kind

    # --- Recouvrement (dunning) ------------------------------------------------
    if kind == "dunning":
        if _has(record, "J+15"):
            sev = "critical"
        elif _has(record, "J+7"):
            sev = "warning"
        else:
            sev = "info"
        return FinancePlan(
            sev, "dunning", "Envoyer la relance (facture impayée)", detail, record_ids=ids
        )

    # --- Trésorerie ------------------------------------------------------------
    if kind == "treasury":
        sev = "critical" if record.important else "info"
        return FinancePlan(
            sev,
            "treasury",
            "Sécuriser la trésorerie (runway sous le seuil)",
            detail,
            record_ids=ids,
        )

    # --- Fiscal (CA3 / IS) — doc fiscal protégé --------------------------------
    if kind == "fiscal":
        return FinancePlan(
            "warning",
            "fiscal",
            "Auditer & déposer la déclaration fiscale (CA3/IS)",
            detail,
            record_ids=ids,
        )

    # --- RGPD ------------------------------------------------------------------
    if kind == "rgpd":
        sev = "critical" if _has(record, "gap", "critical") else "info"
        return FinancePlan(
            sev,
            "rgpd",
            "Régulariser le registre RGPD (traitement non conforme)",
            detail,
            record_ids=ids,
        )

    # --- AI Act ----------------------------------------------------------------
    if kind == "ai_act":
        if _has(record, "prohibited"):
            return FinancePlan(
                "critical",
                "ai_act",
                "Retirer/reclasser un système IA (prohibited — AI Act art. 5)",
                detail,
                record_ids=ids,
            )
        if _has(record, "unclassified"):
            return FinancePlan(
                "warning",
                "ai_act",
                "Classifier les systèmes IA non documentés (AI Act)",
                detail,
                record_ids=ids,
            )
        return None

    # --- Contrats fournisseurs / clients ---------------------------------------
    if kind == "vendor_contract":
        sev = "critical" if _has(record, "missed", "urgent", "critical") else "warning"
        return FinancePlan(
            sev,
            "contract",
            "Annuler/renégocier un contrat fournisseur (échéance)",
            detail,
            record_ids=ids,
        )
    if kind == "client_contract":
        sev = "critical" if _has(record, "expired", "urgent", "critical") else "warning"
        return FinancePlan(
            sev,
            "contract",
            "Préparer le renouvellement d'un contrat client",
            detail,
            record_ids=ids,
        )

    # --- Dépenses --------------------------------------------------------------
    if kind == "expense_anomaly":
        sev = "warning" if record.important else "info"
        return FinancePlan(
            sev, "expense", "Vérifier une anomalie de dépense (Qonto)", detail, record_ids=ids
        )

    # --- Rapprochement bancaire ------------------------------------------------
    if kind == "reconcile" and record.important:
        return FinancePlan(
            "warning",
            "reconcile",
            "Investiguer un mouvement orphelin (rapprochement)",
            detail,
            record_ids=ids,
        )

    # --- Incidents -------------------------------------------------------------
    if kind == "incident":
        return FinancePlan(
            "warning",
            "incident",
            "Compléter le post-mortem d'incident (registre légal)",
            detail,
            record_ids=ids,
        )

    # --- Cross-pôle Vente : devis envoyé → facturer + enregistrer le traitement -
    if kind == "proposal" and _has(record, "sent"):
        return FinancePlan(
            "warning",
            "billing_new",
            "Émettre la facture + enregistrer le nouveau traitement RGPD",
            detail,
            suppressed_by_compliance=compliance_blocking,
            record_ids=ids,
        )

    return None


def plan_actions(records: list[MemoryRecord], *, compliance_blocking: bool) -> list[FinancePlan]:
    """Synthétise un plan d'actions priorisé depuis les faits visibles.

    Tri : sévérité décroissante, puis actions exécutables avant les gelées
    (compliance), puis par type. Stable et déterministe.
    """
    plans = [
        p for r in records if (p := _route(r, compliance_blocking=compliance_blocking)) is not None
    ]
    plans.sort(
        key=lambda p: (severity_rank(p.severity), not p.suppressed_by_compliance, p.kind),
        reverse=True,
    )
    return plans


__all__ = ["FinancePlan", "Severity", "plan_actions", "severity_rank"]
