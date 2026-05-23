"""Parsing de l'Annexe D de ``docs/ARGOS_OPS_PLAN.md`` (P22.G).

Source unique d'avancement de la flotte (depuis 2026-05-23 — voir
commit 4f287a7). Le parser permet à RoadmapPublisher de fabriquer une
roadmap publique sans exposer les codes sprint internes (P22.X, etc.).

Format d'une ligne attendu ::

    - [x] ✅ **BotName** · Role · Description. *Sprint N livré 2026-05-23.*
    - [~] 🟡 **BotName** · Role · Description. *Sprint X partial.*
    - [ ] ⬜ **BotName** · Role · Description. *Sprint X.*
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

# Reconnaît `### N. Titre du service`
_SECTION_RE = re.compile(r"^###\s+\d+\.\s+(?P<title>.+?)\s*$")
# Reconnaît une ligne bot quelle que soit la coche
_BOT_RE = re.compile(
    r"^-\s+\[(?P<state>[ x~])\]\s+(?P<icon>✅|🟡|⬜)?\s*"
    r"\*\*(?P<name>[A-Za-z][\w]*)\*\*\s*·\s*"
    r"(?P<role>[^·]+?)\s*·\s*"
    r"(?P<desc>.+?)\s*"
    r"(?:\*(?P<status>[^*]+)\*)?\s*$"
)


@dataclass(frozen=True)
class BotEntry:
    """Une ligne bot parsée."""

    name: str
    role: str
    description: str
    state: str  # "done" | "partial" | "roadmap"
    status_note: str | None  # texte italique (sprint / date livraison)
    service: str  # ex : "Customer Success & Support"


def parse_annexe_d(path: Path) -> list[BotEntry]:
    """Parse l'Annexe D et retourne toutes les lignes bot avec leur service.

    Retourne une liste vide si le fichier est absent ou ne contient pas
    de section parsable (utilisé par les tests).
    """
    if not path.exists():
        return []
    entries: list[BotEntry] = []
    current_service: str | None = None
    in_annexe = False
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.rstrip()
        if line.startswith("# Annexe D"):
            in_annexe = True
            continue
        if in_annexe and line.startswith("# "):
            # Sortie de l'annexe D (prochain top-level title)
            break
        if not in_annexe:
            continue
        section = _SECTION_RE.match(line)
        if section:
            current_service = section.group("title")
            continue
        if current_service is None:
            continue
        bot = _BOT_RE.match(line)
        if bot is None:
            continue
        state_marker = bot.group("state")
        if state_marker == "x":
            state = "done"
        elif state_marker == "~":
            state = "partial"
        else:
            state = "roadmap"
        entries.append(
            BotEntry(
                name=bot.group("name"),
                role=bot.group("role").strip(),
                description=bot.group("desc").strip().rstrip("."),
                state=state,
                status_note=(bot.group("status") or "").strip() or None,
                service=current_service,
            )
        )
    return entries


def count_states(entries: list[BotEntry]) -> dict[str, int]:
    """Compte le nombre d'entrées par état."""
    counts = {"done": 0, "partial": 0, "roadmap": 0}
    for entry in entries:
        counts[entry.state] += 1
    return counts


__all__ = ["BotEntry", "count_states", "parse_annexe_d"]
