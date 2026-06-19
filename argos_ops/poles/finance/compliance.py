"""Conformité du pôle Finance (archi v2, S5) — registres RGPD + AI Act.

**Garde-fou central du pôle (« le LLM propose, Python tranche »)** — l'analogue
du gel Bloctel de la Vente / du breaker ``ad_spend_runaway`` de Pub.

Deux registres **fichiers** (D-033, local-first) que ce module valide :

- RGPD ``data/poles/finance/compliance/rgpd_registry.yaml`` — chaque traitement
  PII doit déclarer base légale (parmi les 6 de l'art. 6 RGPD), finalité, données,
  durée de conservation, et être revu < 12 mois. Un manque = **gap**.
- AI Act ``data/poles/finance/compliance/ai_act_registry.yaml`` — chaque système
  IA doit porter une classe de risque valide (:func:`classify_ai_act_risk`).
  ``unclassified`` = gap ; ``prohibited`` = bloquant (art. 5).

:func:`compliance_blocking` est ``True`` si un registre est en faute — RGPD
absent / vide / avec un gap, **ou** AI Act absent / vide / contenant un système
``prohibited`` (les deux registres traités symétriquement ; ``unclassified`` AI
Act alerte mais ne bloque pas). Le ``FinanceAgent`` **gèle** alors toute action
d'onboarding d'un nouveau traitement (facturer un nouveau client = nouvelle
collecte PII) tant que la conformité n'est pas régularisée.

Aucun LLM ici, aucune valeur secrète — 100 % déterministe et testable offline.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from argos_ops.compliance import AIActRisk, classify_ai_act_risk
from argos_ops.poles.config import POLES_DIR
from argos_ops.poles.finance.store import dump_yaml_mapping, load_yaml_mapping, parse_date

FINANCE_POLE = "finance"

# Délai au-delà duquel une fiche RGPD est considérée « périmée » (revue annuelle).
RGPD_REVIEW_STALE_DAYS = 365

# Les 6 bases légales de l'art. 6 RGPD (normalisées sans accent / casse).
_VALID_LEGAL_BASES: frozenset[str] = frozenset(
    {
        "consentement",
        "contrat",
        "obligation legale",
        "interet legitime",
        "mission de service public",
        "sauvegarde des interets vitaux",
    }
)

# Champs obligatoires d'une fiche de traitement RGPD.
_REQUIRED_RGPD_FIELDS: tuple[str, ...] = (
    "base_legale",
    "finalite",
    "donnees",
    "duree_conservation",
)


def _normalize(text: str) -> str:
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c)).strip().lower()


def _dict_rows(raw: dict[str, object], key: str) -> list[dict[str, object]]:
    """Extrait une liste de mappings sous ``key`` (vide si absent / mal typé)."""
    value = raw.get(key)
    if not isinstance(value, list):
        return []
    return [r for r in value if isinstance(r, dict)]


# =============================================================================
# Chemins
# =============================================================================
def compliance_dir(*, poles_root: Path = POLES_DIR) -> Path:
    return poles_root / FINANCE_POLE / "compliance"


def rgpd_registry_path(*, poles_root: Path = POLES_DIR) -> Path:
    return compliance_dir(poles_root=poles_root) / "rgpd_registry.yaml"


def ai_act_registry_path(*, poles_root: Path = POLES_DIR) -> Path:
    return compliance_dir(poles_root=poles_root) / "ai_act_registry.yaml"


# =============================================================================
# RGPD
# =============================================================================
@dataclass(frozen=True)
class RGPDTreatment:
    """Une fiche de traitement du registre RGPD + son statut de conformité."""

    nom: str
    base_legale: str
    finalite: str
    duree_conservation: str
    donnees: tuple[str, ...]
    review_date: date | None
    issues: tuple[str, ...]  # vide ⇒ fiche conforme

    @property
    def conforme(self) -> bool:
        return not self.issues


@dataclass(frozen=True)
class RGPDRegistryReport:
    """Bilan de validation du registre RGPD."""

    present: bool
    treatments: tuple[RGPDTreatment, ...]
    should_alert: bool
    summary: str

    @property
    def gaps(self) -> list[RGPDTreatment]:
        return [t for t in self.treatments if not t.conforme]


def _validate_treatment(row: dict[str, object], *, today: date) -> RGPDTreatment:
    nom = str(row.get("nom") or row.get("name") or "(sans nom)")
    issues: list[str] = []
    for field_name in _REQUIRED_RGPD_FIELDS:
        if not row.get(field_name):
            issues.append(f"champ manquant : {field_name}")
    base = str(row.get("base_legale") or "")
    if base and _normalize(base) not in _VALID_LEGAL_BASES:
        issues.append(f"base légale invalide : {base}")
    review_raw = row.get("review_date")
    review_date: date | None = None
    if review_raw is not None:
        try:
            review_date = parse_date(review_raw)
        except (ValueError, TypeError):
            issues.append("review_date illisible")
    if review_date is None:
        issues.append("review_date absente")
    elif (today - review_date).days > RGPD_REVIEW_STALE_DAYS:
        issues.append(f"revue périmée (> {RGPD_REVIEW_STALE_DAYS}j)")
    donnees_raw = row.get("donnees") or []
    donnees = tuple(str(d) for d in donnees_raw) if isinstance(donnees_raw, list) else ()
    return RGPDTreatment(
        nom=nom,
        base_legale=base,
        finalite=str(row.get("finalite") or ""),
        duree_conservation=str(row.get("duree_conservation") or ""),
        donnees=donnees,
        review_date=review_date,
        issues=tuple(issues),
    )


def load_rgpd_registry(
    *, poles_root: Path = POLES_DIR, today: date | None = None
) -> RGPDRegistryReport:
    """Valide le registre RGPD. Absent ⇒ faute professionnelle (alerte)."""
    today = today or date.today()
    path = rgpd_registry_path(poles_root=poles_root)
    if not path.exists():
        return RGPDRegistryReport(
            present=False,
            treatments=(),
            should_alert=True,
            summary="registre RGPD introuvable (FAUTE PROFESSIONNELLE — il DOIT exister)",
        )
    raw = load_yaml_mapping(path)
    treatments = tuple(_validate_treatment(r, today=today) for r in _dict_rows(raw, "traitements"))
    gaps = [t for t in treatments if not t.conforme]
    should_alert = bool(gaps)
    if not treatments:
        summary = "registre RGPD présent mais vide (0 traitement déclaré)"
        should_alert = True
    elif gaps:
        summary = f"{len(gaps)} traitement(s) non conforme(s) sur {len(treatments)}"
    else:
        summary = f"{len(treatments)} traitement(s) RGPD conforme(s)"
    return RGPDRegistryReport(
        present=True,
        treatments=treatments,
        should_alert=should_alert,
        summary=summary,
    )


# =============================================================================
# RGPD — écriture (registre éditable, S5+)
# =============================================================================
def _normalize_donnees(donnees: list[str] | None) -> list[str]:
    """Nettoie la liste de données (retire les entrées vides, strip)."""
    if not donnees:
        return []
    return [d.strip() for d in donnees if d and d.strip()]


def _treatment_row(
    *,
    nom: str,
    base_legale: str,
    finalite: str,
    donnees: list[str],
    duree_conservation: str,
    review_date: str | None,
) -> dict[str, object]:
    """Construit une ligne YAML de traitement RGPD (ordre des clés stable)."""
    row: dict[str, object] = {
        "nom": nom,
        "base_legale": base_legale,
        "finalite": finalite,
        "donnees": donnees,
        "duree_conservation": duree_conservation,
    }
    if review_date is not None:
        row["review_date"] = review_date
    return row


def append_treatment(
    *,
    nom: str,
    base_legale: str,
    finalite: str,
    donnees: list[str],
    duree_conservation: str,
    review_date: str | None,
    poles_root: Path = POLES_DIR,
) -> dict[str, object]:
    """Ajoute un traitement au registre RGPD (réécriture YAML, autres lignes préservées).

    Idempotent par ``nom`` : si une fiche du même nom existe déjà, elle est
    **remplacée** (pas de doublon). Renvoie la ligne persistée.
    """
    path = rgpd_registry_path(poles_root=poles_root)
    raw = load_yaml_mapping(path)
    rows = _dict_rows(raw, "traitements")
    new_row = _treatment_row(
        nom=nom,
        base_legale=base_legale,
        finalite=finalite,
        donnees=_normalize_donnees(donnees),
        duree_conservation=duree_conservation,
        review_date=review_date,
    )
    kept = [r for r in rows if str(r.get("nom") or r.get("name") or "") != nom]
    kept.append(new_row)
    raw["traitements"] = kept
    dump_yaml_mapping(path, raw)
    return new_row


def update_treatment(
    nom: str,
    *,
    base_legale: str,
    finalite: str,
    donnees: list[str],
    duree_conservation: str,
    review_date: str | None,
    poles_root: Path = POLES_DIR,
) -> dict[str, object] | None:
    """Édite la fiche RGPD dont le ``nom`` correspond (en place, clés inconnues préservées).

    ``None`` si aucune fiche ne porte ce ``nom``. Le ``nom`` reste inchangé ; les
    clés non gérées de la ligne (ex. ``sous_traitants``) sont conservées telles
    quelles. Renvoie la ligne mise à jour.
    """
    path = rgpd_registry_path(poles_root=poles_root)
    raw = load_yaml_mapping(path)
    rows = _dict_rows(raw, "traitements")
    target: dict[str, object] | None = None
    out: list[dict[str, object]] = []
    for r in rows:
        if target is None and str(r.get("nom") or r.get("name") or "") == nom:
            merged = dict(r)
            merged.update(
                _treatment_row(
                    nom=nom,
                    base_legale=base_legale,
                    finalite=finalite,
                    donnees=_normalize_donnees(donnees),
                    duree_conservation=duree_conservation,
                    review_date=review_date,
                )
            )
            target = merged
            out.append(merged)
        else:
            out.append(r)
    if target is None:
        return None
    raw["traitements"] = out
    dump_yaml_mapping(path, raw)
    return target


# =============================================================================
# AI Act
# =============================================================================
@dataclass(frozen=True)
class AIActSystem:
    """Un système IA déclaré + sa classe de risque normalisée."""

    nom: str
    role: str
    risk: AIActRisk


@dataclass(frozen=True)
class AIActRegistryReport:
    """Bilan de validation du registre AI Act."""

    present: bool
    systems: tuple[AIActSystem, ...]
    should_alert: bool
    summary: str
    counts: dict[str, int] = field(default_factory=dict)

    @property
    def prohibited(self) -> list[AIActSystem]:
        return [s for s in self.systems if s.risk == "prohibited"]

    @property
    def unclassified(self) -> list[AIActSystem]:
        return [s for s in self.systems if s.risk == "unclassified"]


def load_ai_act_registry(*, poles_root: Path = POLES_DIR) -> AIActRegistryReport:
    """Valide la classification AI Act des systèmes déclarés."""
    path = ai_act_registry_path(poles_root=poles_root)
    if not path.exists():
        return AIActRegistryReport(
            present=False,
            systems=(),
            should_alert=True,
            summary="registre AI Act introuvable (transparence art. 13 non documentée)",
        )
    raw = load_yaml_mapping(path)
    systems = tuple(
        AIActSystem(
            nom=str(r.get("nom") or r.get("name") or "(sans nom)"),
            role=str(r.get("role") or ""),
            risk=classify_ai_act_risk(r.get("risk_class")),
        )
        for r in _dict_rows(raw, "systemes")
    )
    counts = {
        level: sum(1 for s in systems if s.risk == level)
        for level in ("minimal", "limited", "high", "prohibited", "unclassified")
    }
    has_prohibited = counts["prohibited"] > 0
    has_unclassified = counts["unclassified"] > 0
    should_alert = has_prohibited or has_unclassified or not systems
    if not systems:
        summary = "registre AI Act présent mais vide (0 système déclaré)"
    elif has_prohibited:
        summary = f"{counts['prohibited']} système(s) PROHIBITED (AI Act art. 5)"
    elif has_unclassified:
        summary = f"{counts['unclassified']} système(s) non classifié(s)"
    else:
        summary = f"{len(systems)} système(s) IA classifié(s)"
    return AIActRegistryReport(
        present=True,
        systems=systems,
        should_alert=should_alert,
        summary=summary,
        counts=counts,
    )


# =============================================================================
# AI Act — écriture (registre éditable, S5+)
# =============================================================================
def _ai_system_row(*, nom: str, role: str, risk_class: str) -> dict[str, object]:
    """Construit une ligne YAML de système IA (ordre des clés stable)."""
    return {"nom": nom, "role": role, "risk_class": risk_class}


def append_ai_system(
    *,
    nom: str,
    role: str,
    risk_class: str,
    poles_root: Path = POLES_DIR,
) -> dict[str, object]:
    """Ajoute un système au registre AI Act (réécriture YAML, autres lignes préservées).

    Idempotent par ``nom`` : un système du même nom est **remplacé** (pas de
    doublon). La ``risk_class`` est persistée telle quelle ; sa validité est
    re-normalisée à la lecture via :func:`classify_ai_act_risk`. Renvoie la ligne.
    """
    path = ai_act_registry_path(poles_root=poles_root)
    raw = load_yaml_mapping(path)
    rows = _dict_rows(raw, "systemes")
    new_row = _ai_system_row(nom=nom, role=role, risk_class=risk_class)
    kept = [r for r in rows if str(r.get("nom") or r.get("name") or "") != nom]
    kept.append(new_row)
    raw["systemes"] = kept
    dump_yaml_mapping(path, raw)
    return new_row


def update_ai_system(
    nom: str,
    *,
    role: str,
    risk_class: str,
    poles_root: Path = POLES_DIR,
) -> dict[str, object] | None:
    """Édite le système AI Act dont le ``nom`` correspond (en place, clés préservées).

    ``None`` si aucun système ne porte ce ``nom``. Le ``nom`` reste inchangé ;
    les clés non gérées de la ligne sont conservées. Renvoie la ligne mise à jour.
    """
    path = ai_act_registry_path(poles_root=poles_root)
    raw = load_yaml_mapping(path)
    rows = _dict_rows(raw, "systemes")
    target: dict[str, object] | None = None
    out: list[dict[str, object]] = []
    for r in rows:
        if target is None and str(r.get("nom") or r.get("name") or "") == nom:
            merged = dict(r)
            merged.update(_ai_system_row(nom=nom, role=role, risk_class=risk_class))
            target = merged
            out.append(merged)
        else:
            out.append(r)
    if target is None:
        return None
    raw["systemes"] = out
    dump_yaml_mapping(path, raw)
    return target


# =============================================================================
# Garde-fou — « Python tranche »
# =============================================================================
def _ai_act_blocking(ai_act: AIActRegistryReport) -> bool:
    """Le registre AI Act gèle l'onboarding s'il est absent, vide, ou ``prohibited``.

    Symétrique du RGPD (un registre absent/vide = obligation de transparence non
    remplie, alors que le ``FinanceAgent`` est lui-même un système IA). En
    revanche ``unclassified`` reste **non bloquant** (alerte seule) — c'est un gap
    de documentation à combler, pas un interdit art. 5.
    """
    return not ai_act.present or not ai_act.systems or bool(ai_act.prohibited)


def compliance_blocking(*, poles_root: Path = POLES_DIR, today: date | None = None) -> bool:
    """``True`` si la conformité gèle l'onboarding d'un nouveau traitement.

    Bloquant quand : le registre RGPD est absent / vide / a un gap, **ou** le
    registre AI Act est absent / vide / contient un système ``prohibited``. Tant
    que c'est vrai, on n'enregistre pas de nouvelle collecte PII (facturer un
    nouveau client). ``unclassified`` AI Act reste non bloquant (alerte seule).
    """
    rgpd = load_rgpd_registry(poles_root=poles_root, today=today)
    ai_act = load_ai_act_registry(poles_root=poles_root)
    return rgpd.should_alert or _ai_act_blocking(ai_act)


def blocking_reason(*, poles_root: Path = POLES_DIR, today: date | None = None) -> str:
    """Phrase courte expliquant le gel conformité (vide si non bloquant)."""
    rgpd = load_rgpd_registry(poles_root=poles_root, today=today)
    ai_act = load_ai_act_registry(poles_root=poles_root)
    reasons: list[str] = []
    if rgpd.should_alert:
        reasons.append(f"RGPD — {rgpd.summary}")
    if _ai_act_blocking(ai_act):
        reasons.append(f"AI Act — {ai_act.summary}")
    return " ; ".join(reasons)


__all__ = [
    "RGPD_REVIEW_STALE_DAYS",
    "AIActRegistryReport",
    "AIActSystem",
    "RGPDRegistryReport",
    "RGPDTreatment",
    "ai_act_registry_path",
    "append_ai_system",
    "append_treatment",
    "blocking_reason",
    "compliance_blocking",
    "compliance_dir",
    "load_ai_act_registry",
    "load_rgpd_registry",
    "rgpd_registry_path",
    "update_ai_system",
    "update_treatment",
]
