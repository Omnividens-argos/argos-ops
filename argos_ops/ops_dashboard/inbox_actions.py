"""Mutations sur les drafts de l'Inbox (Phase 2 UX).

Permet à l'UI de marquer un draft comme ``validated`` ou ``rejected`` sans
ouvrir l'éditeur Markdown — la mutation se fait sur le frontmatter YAML
du fichier markdown directement (idempotente, conserve le corps).

Sécurité : on accepte uniquement les ``id`` qui ressortent du scanner
``inbox_scanner.scan_inbox_drafts()`` — pas de chemin libre côté API.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path

from fastapi import HTTPException
from loguru import logger

from argos_ops.ops_dashboard.inbox_scanner import _project_root, scan_inbox_drafts


def _resolve_draft_path(draft_id: str) -> Path:
    """Vérifie que ``draft_id`` correspond à un draft pending connu.

    Le scanner ré-évalue dynamiquement les drafts à chaque appel — on s'appuie
    dessus comme source de vérité plutôt que de stocker un index en mémoire.
    """
    drafts = scan_inbox_drafts()
    match = next((d for d in drafts if d.id == draft_id), None)
    if match is None:
        raise HTTPException(
            status_code=404,
            detail=f"Draft introuvable ou déjà traité : {draft_id}",
        )
    path = (_project_root() / match.file_path).resolve()
    root = _project_root().resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Chemin draft hors repo") from exc
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Fichier draft disparu")
    return path


def _patch_frontmatter(text: str, updates: dict[str, str]) -> str:
    """Insère / remplace des clés dans le bloc frontmatter YAML d'un .md.

    Ne touche pas au corps du markdown. Si le frontmatter n'existe pas, il
    est créé en tête du fichier (rare — les drafts en ont quasi toujours).
    Si une clé existe déjà, sa valeur est écrasée.
    """
    if not text.startswith("---"):
        # Crée un frontmatter minimal en préfixe.
        lines = [f"{k}: {v}" for k, v in updates.items()]
        return "---\n" + "\n".join(lines) + "\n---\n\n" + text

    end_idx = text.find("\n---", 3)
    if end_idx == -1:
        # Frontmatter mal formé — fallback création.
        lines = [f"{k}: {v}" for k, v in updates.items()]
        return "---\n" + "\n".join(lines) + "\n---\n\n" + text

    block = text[3:end_idx]
    body = text[end_idx + 4 :]  # skip "\n---"

    block_lines = block.splitlines()
    remaining = dict(updates)
    out_lines: list[str] = []
    for line in block_lines:
        match = re.match(r"^([\w-]+)\s*:", line)
        if match and match.group(1).lower() in remaining:
            key = match.group(1).lower()
            value = remaining.pop(key)
            out_lines.append(f"{match.group(1)}: {value}")
        else:
            out_lines.append(line)
    for k, v in remaining.items():
        out_lines.append(f"{k}: {v}")

    return "---\n" + "\n".join(out_lines).strip("\n") + "\n---" + body


def validate_draft(draft_id: str, *, note: str | None = None) -> Path:
    """Passe ``status`` à ``validated`` + horodate ``validated_at``."""
    path = _resolve_draft_path(draft_id)
    now = datetime.now(UTC).isoformat(timespec="seconds")
    text = path.read_text(encoding="utf-8")
    updates: dict[str, str] = {
        "status": "validated",
        "validated_at": f'"{now}"',
    }
    if note:
        # On ne tente pas du multi-ligne ici (parser simple) — on tronque + escape.
        sanitized = note.replace("\n", " ").replace('"', "'")[:280]
        updates["validation_note"] = f'"{sanitized}"'
    patched = _patch_frontmatter(text, updates)
    path.write_text(patched, encoding="utf-8")
    logger.info("inbox_actions: validated {}", draft_id)
    return path


def reject_draft(draft_id: str, *, reason: str | None = None) -> Path:
    """Passe ``status`` à ``rejected`` + horodate + raison optionnelle."""
    path = _resolve_draft_path(draft_id)
    now = datetime.now(UTC).isoformat(timespec="seconds")
    text = path.read_text(encoding="utf-8")
    updates: dict[str, str] = {
        "status": "rejected",
        "rejected_at": f'"{now}"',
    }
    if reason:
        sanitized = reason.replace("\n", " ").replace('"', "'")[:280]
        updates["rejection_reason"] = f'"{sanitized}"'
    patched = _patch_frontmatter(text, updates)
    path.write_text(patched, encoding="utf-8")
    logger.info("inbox_actions: rejected {} ({})", draft_id, reason or "no reason")
    return path


__all__ = ["reject_draft", "validate_draft"]
