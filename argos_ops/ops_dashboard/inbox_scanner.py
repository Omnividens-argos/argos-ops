"""Scanner filesystem pour l'Inbox unifiée du Admin Control Panel.

Parcourt ``data/`` à la recherche des drafts markdown produits par les bots
et retourne ceux qui sont encore en attente de validation humaine. Pas de
DB ici — la source de vérité reste le filesystem (cf. D-017 local-first).

Catégories scannées :
  - email     : data/outbound/enriched, data/outbound/sequences
  - social    : data/content/drafts (LinkedIn, Mastodon)
  - proposal  : data/proposals, data/contracts
  - seo       : data/seo/briefs, data/blog/drafts
  - press     : data/comm/press_releases, data/comm/crisis_responses
  - doc       : docs/adr (status=draft), data/release_notes/drafts

Filtrés OUT : status ∈ {validated, posted, sent, published, signed}.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from loguru import logger

from argos_ops.ops_dashboard.models import InboxDraft

InboxKind = Literal["email", "social", "proposal", "seo", "press", "doc", "other"]

# Statuts qui signifient "pas encore validé / envoyé" → restent dans l'Inbox.
_PENDING_STATUSES: frozenset[str] = frozenset(
    {
        "draft",
        "drafted",
        "pending",
        "pending_review",
        "needs_review",
        "queued",
        "scheduled",
    }
)

# Statuts qui sortent l'item de l'inbox (déjà traité par le founder).
_FINAL_STATUSES: frozenset[str] = frozenset(
    {
        "validated",
        "posted",
        "sent",
        "published",
        "signed",
        "rejected",
        "killed",
        "archived",
    }
)


def _project_root() -> Path:
    """Racine du repo (parent de ``argos_ops/``)."""
    return Path(__file__).resolve().parents[2]


def _parse_frontmatter(text: str) -> dict[str, str]:
    """Parse minimaliste de frontmatter YAML (key: value sur une ligne).

    On évite d'embarquer PyYAML ici parce qu'on n'a besoin que de quelques
    champs scalaires (``status``, ``date_created``, ``topic``...). Si une
    valeur a un format complexe (liste, multiligne), on la skip — le
    frontend tolère ``None``.
    """
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end == -1:
        return {}
    block = text[3:end]
    out: dict[str, str] = {}
    for line in block.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        match = re.match(r"^([\w-]+)\s*:\s*(.*)$", stripped)
        if not match:
            continue
        key, value = match.group(1).lower(), match.group(2).strip()
        # Strip quotes simples / doubles autour de la valeur.
        if (value.startswith('"') and value.endswith('"')) or (
            value.startswith("'") and value.endswith("'")
        ):
            value = value[1:-1]
        out[key] = value
    return out


def _normalize_status(raw: str | None) -> str:
    """Normalise les valeurs de status pour matcher les sets de filtre."""
    if not raw:
        return "draft"
    return raw.strip().lower().strip('"').strip("'")


def _parse_created_at(meta: dict[str, str], fallback: Path) -> datetime:
    """Tente plusieurs champs date, fallback sur mtime du fichier."""
    for key in ("date_created", "created_at", "date", "drafted_at", "scheduled_for"):
        raw = meta.get(key)
        if raw and raw.lower() not in ("null", "none", ""):
            for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
                try:
                    return datetime.strptime(raw[: len(fmt) + 2], fmt).replace(tzinfo=UTC)
                except ValueError:
                    continue
    try:
        return datetime.fromtimestamp(fallback.stat().st_mtime, tz=UTC)
    except OSError:
        return datetime.now(UTC)


def _build_title(meta: dict[str, str], path: Path) -> str:
    """Choisit le meilleur libellé disponible pour afficher l'item dans l'UI."""
    for key in ("title", "topic", "subject", "headline", "deal_id", "slug"):
        if value := meta.get(key):
            return value
    return path.stem.replace("-", " ").replace("_", " ")


def _build_summary(meta: dict[str, str]) -> str | None:
    for key in ("angle", "summary", "preview_text", "tagline", "body_preview"):
        if value := meta.get(key):
            return value[:280]
    return None


def _scan_directory(
    root: Path,
    rel_pattern: str,
    *,
    kind: InboxKind,
    agent_name: str | None,
    include_all_statuses: bool = False,
) -> list[InboxDraft]:
    """Scan récursif d'un dossier pour un kind donné.

    ``rel_pattern`` est une glob ancrée à ``root`` (ex : ``content/drafts/*.md``).
    ``include_all_statuses=True`` désactive le filtre pending/final (utilisé par
    l'Outputs library qui veut voir TOUS les drafts produits).
    """
    drafts: list[InboxDraft] = []
    matches = list(root.glob(rel_pattern))
    for path in matches:
        if not path.is_file() or path.suffix.lower() != ".md":
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            logger.warning("inbox_scanner: cannot read {} → {}", path, exc)
            continue
        meta = _parse_frontmatter(text)
        status = _normalize_status(meta.get("status"))
        if not include_all_statuses:
            if status in _FINAL_STATUSES:
                continue
            # Tolérant : si pas de status explicite, on considère que c'est un draft.
            if status not in _PENDING_STATUSES and "status" in meta:
                continue
        drafts.append(
            InboxDraft(
                id=str(path.relative_to(root)).replace("\\", "/"),
                kind=kind,
                title=_build_title(meta, path),
                summary=_build_summary(meta),
                status=status or "draft",
                created_at=_parse_created_at(meta, path),
                file_path=str(path.relative_to(root)).replace("\\", "/"),
                agent_name=agent_name,
            )
        )
    return drafts


def _scan_all_sources(*, include_all_statuses: bool) -> list[InboxDraft]:
    """Implémentation partagée entre scan_inbox_drafts (pending only) et
    scan_all_outputs (everything, validated/rejected/posted inclus).
    """
    root = _project_root()
    out: list[InboxDraft] = []

    # Social — ContentBot drafts (P9)
    out.extend(
        _scan_directory(
            root,
            "data/content/drafts/*.md",
            kind="social",
            agent_name="ContentBot",
            include_all_statuses=include_all_statuses,
        )
    )

    # Email outbound — OutboundBot sequences (P13.A shadow)
    out.extend(
        _scan_directory(
            root,
            "data/outbound/sequences/**/*.md",
            kind="email",
            agent_name="OutboundBot",
            include_all_statuses=include_all_statuses,
        )
    )
    out.extend(
        _scan_directory(
            root,
            "data/outbound/enriched/*.md",
            kind="email",
            agent_name="LeadEnricher",
            include_all_statuses=include_all_statuses,
        )
    )

    # SEO briefs
    out.extend(
        _scan_directory(
            root,
            "data/seo/briefs/*.md",
            kind="seo",
            agent_name="SEOBot",
            include_all_statuses=include_all_statuses,
        )
    )
    out.extend(
        _scan_directory(
            root,
            "data/blog/drafts/*.md",
            kind="seo",
            agent_name="CaseStudyDrafter",
            include_all_statuses=include_all_statuses,
        )
    )

    # Proposals / contracts
    out.extend(
        _scan_directory(
            root,
            "data/proposals/**/*.md",
            kind="proposal",
            agent_name="ProposalBot",
            include_all_statuses=include_all_statuses,
        )
    )
    out.extend(
        _scan_directory(
            root,
            "data/contracts/**/*.md",
            kind="proposal",
            agent_name="ContractGenerator",
            include_all_statuses=include_all_statuses,
        )
    )

    # Press / crisis
    out.extend(
        _scan_directory(
            root,
            "data/comm/press_releases/**/*.md",
            kind="press",
            agent_name="PressReleaseDrafter",
            include_all_statuses=include_all_statuses,
        )
    )
    out.extend(
        _scan_directory(
            root,
            "data/comm/crisis_responses/**/*.md",
            kind="press",
            agent_name="CrisisCommBot",
            include_all_statuses=include_all_statuses,
        )
    )

    # Internal docs (ADRs, release notes drafts)
    out.extend(
        _scan_directory(
            root,
            "docs/adr/*.md",
            kind="doc",
            agent_name="ADRWriter",
            include_all_statuses=include_all_statuses,
        )
    )
    out.extend(
        _scan_directory(
            root,
            "data/release_notes/drafts/*.md",
            kind="doc",
            agent_name="ReleaseNotesBot",
            include_all_statuses=include_all_statuses,
        )
    )

    out.sort(key=lambda d: d.created_at, reverse=True)
    return out


def scan_inbox_drafts() -> list[InboxDraft]:
    """Drafts en attente d'action humaine — feed de /api/inbox/drafts."""
    return _scan_all_sources(include_all_statuses=False)


def scan_all_outputs() -> list[InboxDraft]:
    """TOUS les drafts produits, peu importe leur status — feed de
    /api/outputs/index (Phase 4 UX). Permet à l'Outputs library de montrer
    aussi les drafts validés, rejetés, posted, etc.
    """
    return _scan_all_sources(include_all_statuses=True)


def read_output_content(file_path: str) -> str:
    """Lit le contenu raw d'un draft, après vérif que le chemin est sous repo.

    Sécurité : refuse tout chemin contenant ``..`` ou pointant hors du repo.
    Refuse aussi les extensions autres que ``.md`` (read-only markdown only).
    """
    from fastapi import HTTPException

    if ".." in file_path:
        raise HTTPException(status_code=400, detail="Chemin invalide")
    root = _project_root().resolve()
    target = (root / file_path).resolve()
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Chemin hors repo") from exc
    if not target.is_file():
        raise HTTPException(status_code=404, detail="Fichier introuvable")
    if target.suffix.lower() != ".md":
        raise HTTPException(
            status_code=400,
            detail=f"Extension {target.suffix} non lisible depuis le panel (markdown only).",
        )
    try:
        return target.read_text(encoding="utf-8")
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"Lecture échouée : {exc}") from exc


__all__ = ["read_output_content", "scan_all_outputs", "scan_inbox_drafts"]
