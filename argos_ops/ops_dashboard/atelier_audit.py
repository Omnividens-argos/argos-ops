"""Journal d'audit append-only des actions de l'atelier embarqué (Axe 4, D-029).

L'atelier est RCE-par-conception (Claude Code piloté localement). Ce module
trace chaque action irréversible ou semi-sensible pour répondre à « qui a
approuvé/exécuté quoi, quand, dans quel mode » :

- ``console_act`` — la gâchette AGIR (approbation humaine + exécution réelle) ;
- tour atelier — mode ``read`` / ``fleet``, prompt tronqué + redacté ;
- MCP ``run_bot`` / ``remember_fact`` — pilotage flotte depuis l'atelier.

Garanties :
- **Local-only** : le journal contient prompts + IP → ``data/atelier_audit/``
  est gitignoré, jamais committé.
- **Anti-fuite** : la ligne JSON ENTIÈRE passe par
  :func:`argos_ops.logging.redact_secrets` avant écriture (le filtre loguru ne
  couvre pas un ``open().write`` direct) + le prompt est tronqué.
- **Best-effort** : un échec d'écriture d'audit ne casse JAMAIS l'action
  (``try/except`` large + ``logger.warning``). Un atelier qui plante parce que
  le disque est plein serait pire que pas d'audit.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

from loguru import logger

from argos_ops.config import REPO_ROOT
from argos_ops.logging import redact_secrets

AUDIT_DIR = REPO_ROOT / "data" / "atelier_audit"
_EXCERPT_MAX = 280


@dataclass(frozen=True)
class AuditEvent:
    """Une entrée d'audit atelier. Tous les champs optionnels sauf ``action``."""

    action: str  # atelier_turn | console_act | mcp_run_bot | mcp_remember_fact
    mode: str | None = None  # read | fleet | console
    bot: str | None = None
    prompt_excerpt: str | None = None
    verdict: str | None = None  # auto_send | queued | killed
    approved: bool | None = None
    acted: bool = False
    live: bool | None = None  # SHADOW (False) vs LIVE (True) au moment de l'action
    outcome: str | None = (
        None  # executed | blocked_killed | blocked_not_approved | not_runnable | error
    )
    result_status: str | None = None
    result_error: str | None = None
    session_id: str | None = None
    client_ip: str | None = None


def excerpt(text: str | None) -> str | None:
    """Redacte PUIS tronque un prompt à :data:`_EXCERPT_MAX` chars.

    L'ordre compte : redacter d'abord évite qu'un secret à cheval sur le seuil
    de troncature laisse un préfixe non redacté (trop court pour matcher le
    pattern après coup).
    """
    if not text:
        return None
    trimmed = redact_secrets(text.strip())
    return trimmed[:_EXCERPT_MAX] + ("…" if len(trimmed) > _EXCERPT_MAX else "")


def _audit_path(now: datetime) -> Path:
    return AUDIT_DIR / f"atelier-{now:%Y-%m-%d}.jsonl"


def record(event: AuditEvent, *, now: datetime | None = None) -> None:
    """Écrit 1 ligne JSON redactée (append-only, rotation journalière).

    Best-effort : ne lève jamais. Le ``record`` au point d'action doit être
    invisible si l'audit échoue (l'action prime sur sa trace).
    """
    try:
        stamp = now or datetime.now(UTC)
        payload = {"ts": stamp.isoformat(), **asdict(event)}
        line = redact_secrets(json.dumps(payload, ensure_ascii=False))
        AUDIT_DIR.mkdir(parents=True, exist_ok=True)
        with _audit_path(stamp).open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
    except Exception as exc:  # audit best-effort, ne doit jamais bloquer l'action
        logger.warning(f"atelier_audit — échec d'écriture (ignoré) : {exc}")


__all__ = ["AUDIT_DIR", "AuditEvent", "excerpt", "record"]
