"""Historique des conversations Claude de l'Atelier libre (Cockpit).

Claude Code journalise chaque session en JSONL sous
``~/.claude/projects/<cwd-encodé>/<session-id>.jsonl``. Ce module liste les
anciennes sessions de ce repo et relit un transcript, pour pouvoir **rouvrir et
reprendre** une conversation (le `session_id` est ré-injecté via ``--resume``).

100 % lecture locale, aucune écriture. Aucun secret manipulé.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from argos_ops.config import REPO_ROOT

# Un session-id Claude = UUID ; on n'accepte que ce charset pour fabriquer le
# chemin (anti path-traversal).
_SESSION_ID_RE = re.compile(r"^[A-Za-z0-9._-]+$")


def sessions_dir(repo_root: Path = REPO_ROOT) -> Path:
    """Dossier des transcripts Claude pour ce repo.

    Claude encode le cwd en remplaçant ``:`` ``\\`` ``/`` par ``-`` (et
    minusculise la lettre de lecteur Windows). On teste les deux variantes.
    """
    encoded = str(repo_root).replace(":", "-").replace("\\", "-").replace("/", "-")
    base = Path.home() / ".claude" / "projects"
    for name in (encoded, encoded[:1].lower() + encoded[1:]):
        candidate = base / name
        if candidate.is_dir():
            return candidate
    return base / encoded


@dataclass
class SessionMeta:
    id: str
    title: str
    updated_at: str  # ISO 8601


def _content_text(content: Any) -> str:
    """Texte d'un champ ``content`` (str, ou liste de blocs ``{type,text}``)."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = [
            str(b.get("text", ""))
            for b in content
            if isinstance(b, dict) and b.get("type") == "text"
        ]
        return "\n".join(p for p in parts if p)
    return ""


def _session_path(session_id: str, repo_root: Path) -> Path | None:
    if not _SESSION_ID_RE.match(session_id):
        return None
    base = sessions_dir(repo_root)
    path = (base / f"{session_id}.jsonl").resolve()
    # Garde-fou : le fichier résolu doit rester dans le dossier des sessions.
    if base.resolve() not in path.parents:
        return None
    return path if path.is_file() else None


def _first_user_text(path: Path, limit: int = 90) -> str:
    try:
        with path.open(encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if obj.get("type") == "user":
                    text = _content_text((obj.get("message") or {}).get("content"))
                    flat = " ".join(text.split())
                    if flat:
                        return flat if len(flat) <= limit else flat[: limit - 1] + "…"
    except OSError:
        return ""
    return "(sans titre)"


def list_sessions(repo_root: Path = REPO_ROOT, *, limit: int = 50) -> list[SessionMeta]:
    """Liste les sessions Claude de ce repo, plus récentes d'abord."""
    base = sessions_dir(repo_root)
    if not base.is_dir():
        return []
    files = sorted(base.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
    out: list[SessionMeta] = []
    for path in files[:limit]:
        updated = datetime.fromtimestamp(path.stat().st_mtime, tz=UTC).isoformat()
        out.append(SessionMeta(id=path.stem, title=_first_user_text(path), updated_at=updated))
    return out


def read_transcript(
    session_id: str, repo_root: Path = REPO_ROOT, *, max_items: int = 500
) -> list[dict[str, str]]:
    """Relit un transcript en items rendus par le front.

    Chaque item : ``{role: user|assistant|tool|tool_result, text}`` (+ ``name``
    pour les outils). Robuste : lignes non-JSON ignorées.
    """
    path = _session_path(session_id, repo_root)
    if path is None:
        return []
    items: list[dict[str, str]] = []
    with path.open(encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            etype = obj.get("type")
            if etype not in ("user", "assistant"):
                continue
            content = (obj.get("message") or {}).get("content")
            if isinstance(content, str):
                if content.strip():
                    items.append({"role": etype, "text": content})
                continue
            if not isinstance(content, list):
                continue
            for block in content:
                if not isinstance(block, dict):
                    continue
                btype = block.get("type")
                if btype == "text" and str(block.get("text", "")).strip():
                    items.append({"role": etype, "text": str(block["text"])})
                elif btype == "tool_use":
                    items.append({"role": "tool", "text": "", "name": str(block.get("name", "?"))})
                elif btype == "tool_result":
                    items.append(
                        {"role": "tool_result", "text": _content_text(block.get("content"))}
                    )
    return items[:max_items]


__all__ = ["SessionMeta", "list_sessions", "read_transcript", "sessions_dir"]
