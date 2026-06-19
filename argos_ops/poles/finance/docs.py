"""Génération de documents du pôle Finance (archi v2, S5).

Produit les documents fiscaux / commerciaux du pôle dans
``data/poles/finance/docs/`` et tente un rendu PDF (preview) via
:func:`argos_ops.sales.templates.try_render_pdf` (pandoc si dispo — sinon
Markdown seul, D-009) :

- **CA3** (TVA) : depuis le MRR proxy (:func:`argos_ops.poles.finance.taxes.current_ca3`) ;
- **devis / contrat** : depuis un contexte ``docs/contexts/<deal>.yaml``
  (:class:`argos_ops.sales.models.ProposalContext`) via
  :func:`render_proposal` / :func:`render_contract`.

Gère aussi l'**upload** de documents à remplir (``docs/uploads/``) et la lecture
du Markdown pour la preview cockpit. Aucune valeur secrète (D-017).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Literal

from loguru import logger

from argos_ops.poles.config import POLES_DIR
from argos_ops.poles.finance.store import load_yaml_mapping, parse_date
from argos_ops.poles.finance.taxes import current_ca3, is_forecast, render_tax_markdown
from argos_ops.sales.models import ProposalContext
from argos_ops.sales.templates import render_contract, render_proposal, try_render_pdf

FINANCE_POLE = "finance"
DocKind = Literal["ca3", "forecast", "proposal", "contract", "upload", "other"]

_RESERVED_SUBDIRS = {"contexts", "uploads", "dunning"}


# =============================================================================
# Chemins
# =============================================================================
def docs_dir(*, poles_root: Path = POLES_DIR) -> Path:
    return poles_root / FINANCE_POLE / "docs"


def contexts_dir(*, poles_root: Path = POLES_DIR) -> Path:
    return docs_dir(poles_root=poles_root) / "contexts"


def uploads_dir(*, poles_root: Path = POLES_DIR) -> Path:
    return docs_dir(poles_root=poles_root) / "uploads"


# =============================================================================
# Vue cockpit
# =============================================================================
@dataclass(frozen=True)
class DocEntry:
    """Un document généré + son statut PDF."""

    name: str  # nom de fichier markdown (ex. ca3_2026-05.md)
    kind: DocKind
    has_pdf: bool


def _classify(name: str) -> DocKind:
    if name.startswith("ca3_"):
        return "ca3"
    if name.startswith("forecast_"):
        return "forecast"
    if name.startswith("proposal_") or name.startswith("devis_"):
        return "proposal"
    if name.startswith("contract_") or name.startswith("contrat_"):
        return "contract"
    return "other"


def list_docs(*, poles_root: Path = POLES_DIR) -> list[DocEntry]:
    """Liste les docs markdown générés (hors sous-dossiers réservés). Best-effort."""
    d = docs_dir(poles_root=poles_root)
    if not d.exists():
        return []
    out: list[DocEntry] = []
    for path in sorted(d.glob("*.md")):
        out.append(
            DocEntry(
                name=path.name,
                kind=_classify(path.stem),
                has_pdf=path.with_suffix(".pdf").exists(),
            )
        )
    return out


def read_doc(name: str, *, poles_root: Path = POLES_DIR) -> str | None:
    """Contenu markdown d'un doc pour la preview cockpit. ``None`` si absent.

    Restreint aux **enfants directs** de ``docs/`` (mêmes docs que ``list_docs``)
    : anti-traversal **et** pas de lecture des sous-dossiers réservés
    (``contexts/`` / ``uploads/`` / ``dunning/``). Un ``name`` contenant un
    séparateur (``/`` ou ``\\``) est donc rejeté.
    """
    base = docs_dir(poles_root=poles_root).resolve()
    path = (base / name).resolve()
    if path.parent != base or path.suffix != ".md" or not path.exists():
        return None
    return path.read_text(encoding="utf-8")


def pdf_path(name: str, *, poles_root: Path = POLES_DIR) -> Path | None:
    """Chemin du PDF généré (``docs/<name>.pdf``) pour téléchargement. ``None`` si absent.

    Mêmes garde-fous que :func:`read_doc` : restreint aux **enfants directs** de
    ``docs/`` (anti-traversal — un ``name`` contenant un séparateur est rejeté) et
    suffixe ``.pdf`` exigé. ``None`` si le fichier n'existe pas (PDF non rendu —
    pandoc absent, D-009).
    """
    base = docs_dir(poles_root=poles_root).resolve()
    path = (base / name).resolve()
    if path.parent != base or path.suffix != ".pdf" or not path.exists():
        return None
    return path


def list_context_ids(*, poles_root: Path = POLES_DIR) -> list[str]:
    """Slugs de deal ayant un contexte devis/contrat (``docs/contexts/<id>.yaml``)."""
    d = contexts_dir(poles_root=poles_root)
    if not d.exists():
        return []
    return sorted(p.stem for p in d.glob("*.yaml"))


def _as_int(value: object, default: int) -> int:
    """Coercion défensive d'une valeur YAML en int (sans casser le typage strict)."""
    if isinstance(value, bool):
        return default
    if isinstance(value, (int, str)):
        try:
            return int(value)
        except ValueError:
            return default
    return default


def _load_context(deal_id: str, *, poles_root: Path = POLES_DIR) -> ProposalContext | None:
    path = contexts_dir(poles_root=poles_root) / f"{deal_id}.yaml"
    if not path.exists():
        return None
    raw = load_yaml_mapping(path)
    if not raw.get("company"):
        return None
    issue_raw = raw.get("issue_date")
    extras_raw = raw.get("extras") or {}
    return ProposalContext(
        deal_id=str(raw.get("deal_id", deal_id)),
        company=str(raw["company"]),
        contact_name=str(raw.get("contact_name", "")),
        contact_email=str(raw.get("contact_email", "")),
        siret=(str(raw["siret"]) if raw.get("siret") else None),
        plan=str(raw.get("plan", "Argos Pro")),
        monthly_price_eur=_as_int(raw.get("monthly_price_eur"), 350),
        setup_fee_eur=_as_int(raw.get("setup_fee_eur"), 0),
        discount_percent=_as_int(raw.get("discount_percent"), 0),
        contract_duration_months=_as_int(raw.get("contract_duration_months"), 12),
        issue_date=parse_date(issue_raw) if issue_raw else date.today(),
        validity_days=_as_int(raw.get("validity_days"), 30),
        extras={str(k): str(v) for k, v in extras_raw.items()}
        if isinstance(extras_raw, dict)
        else {},
    )


# =============================================================================
# Génération
# =============================================================================
def _write_with_pdf(name: str, markdown: str, *, poles_root: Path) -> Path:
    """Écrit le markdown + tente le PDF. Renvoie le chemin markdown."""
    d = docs_dir(poles_root=poles_root)
    d.mkdir(parents=True, exist_ok=True)
    md_path = d / name
    md_path.write_text(markdown, encoding="utf-8")
    pdf_ok = try_render_pdf(md_path, pdf_path=md_path.with_suffix(".pdf"))
    if not pdf_ok:
        logger.debug(f"finance/docs — pandoc absent, {name} en Markdown seul (D-009)")
    return md_path


def generate_ca3(
    *,
    poles_root: Path = POLES_DIR,
    period_month: str | None = None,
    projected_annual_profit_eur: Decimal | None = None,
    today: date | None = None,
) -> Path:
    """Génère la CA3 (TVA) du mois + IS prévisionnel optionnel. Re-rend à chaque appel."""
    ca3 = current_ca3(poles_root=poles_root, period_month=period_month, today=today)
    isf = is_forecast(projected_annual_profit_eur) if projected_annual_profit_eur else None
    markdown = render_tax_markdown(ca3, isf)
    return _write_with_pdf(f"ca3_{ca3.period_month}.md", markdown, poles_root=poles_root)


def generate_proposal(deal_id: str, *, poles_root: Path = POLES_DIR) -> Path | None:
    """Génère un devis depuis ``docs/contexts/<deal>.yaml``. ``None`` si absent."""
    ctx = _load_context(deal_id, poles_root=poles_root)
    if ctx is None:
        return None
    return _write_with_pdf(f"devis_{deal_id}.md", render_proposal(ctx), poles_root=poles_root)


def generate_contract(deal_id: str, *, poles_root: Path = POLES_DIR) -> Path | None:
    """Génère un contrat depuis ``docs/contexts/<deal>.yaml``. ``None`` si absent."""
    ctx = _load_context(deal_id, poles_root=poles_root)
    if ctx is None:
        return None
    return _write_with_pdf(f"contrat_{deal_id}.md", render_contract(ctx), poles_root=poles_root)


def save_upload(filename: str, content: str, *, poles_root: Path = POLES_DIR) -> Path:
    """Enregistre un document à remplir (uploadé). Sanitize le nom (anti-traversal)."""
    safe = Path(filename).name or "document.md"
    d = uploads_dir(poles_root=poles_root)
    d.mkdir(parents=True, exist_ok=True)
    path = d / safe
    path.write_text(content, encoding="utf-8")
    return path


def list_uploads(*, poles_root: Path = POLES_DIR) -> list[str]:
    d = uploads_dir(poles_root=poles_root)
    if not d.exists():
        return []
    return sorted(p.name for p in d.iterdir() if p.is_file())


__all__ = [
    "DocEntry",
    "DocKind",
    "contexts_dir",
    "docs_dir",
    "generate_ca3",
    "generate_contract",
    "generate_proposal",
    "list_context_ids",
    "list_docs",
    "list_uploads",
    "pdf_path",
    "read_doc",
    "save_upload",
    "uploads_dir",
]
