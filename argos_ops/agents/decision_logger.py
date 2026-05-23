"""DecisionLogger — Knowledge Steward (P22.E Direction Sprint 9).

Append une décision structurante au journal canonique
``docs/DECISIONS.md`` selon le template documenté en fin de fichier.

Mode interactif via slash ``/log-decision`` — Claude collecte les inputs
(titre, partie du plan, décision, pourquoi, implication technique,
annule, action de suivi), trouve le prochain ID ``D-NNN`` libre, et
appelle :func:`append_decision`.

**Garde-fou tests** : ne JAMAIS écrire le vrai ``docs/DECISIONS.md`` en
mode test. Le slash command et les tests passent un ``output_path``
explicite — par défaut, le slash écrit dans le journal canonique mais
le bot lui-même refuse d'écrire si l'output_path n'est pas explicitement
fourni à l'instanciation.

Cf. plan ``docs/ARGOS_OPS_PLAN.md`` Annexe D § 1 Direction, Sprint 9.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path

from loguru import logger

from argos_ops.agents.base import BaseAgent, RunResult
from argos_ops.config import REPO_ROOT

DEFAULT_DECISIONS_PATH: Path = REPO_ROOT / "docs" / "DECISIONS.md"

# Pattern strict : début de ligne, espaces optionnels, ## D-NNN
_DECISION_HEADER_RE = re.compile(r"^##\s+D-(\d{3})\s+", re.MULTILINE)


@dataclass(frozen=True)
class DecisionDraft:
    """Une décision en attente d'écriture."""

    title: str
    partie: str
    decision: str
    pourquoi: str
    implication_technique: str | None = None
    annule: str | None = None
    action_de_suivi: str | None = None


@dataclass(frozen=True)
class DecisionWriteResult:
    """Résultat d'une écriture de décision."""

    decision_id: str  # D-XXX
    path: Path
    appended: bool


# =============================================================================
# Détection ID libre
# =============================================================================
def find_next_decision_id(decisions_md: str) -> str:
    """Retourne le prochain ID ``D-NNN`` libre, format zero-padded."""
    used = [int(m.group(1)) for m in _DECISION_HEADER_RE.finditer(decisions_md)]
    next_n = (max(used) + 1) if used else 1
    return f"D-{next_n:03d}"


# =============================================================================
# Rendu template
# =============================================================================
def render_decision(
    draft: DecisionDraft, *, decision_id: str, today: date
) -> str:
    """Rend un bloc markdown ``## D-NNN — Titre`` selon le template canonique."""
    lines = [
        f"## {decision_id} — {draft.title}",
        f"**Date :** {today.isoformat()}",
        f"**Partie :** {draft.partie}",
        f"**Décision :** {draft.decision}",
        f"**Pourquoi :** {draft.pourquoi}",
    ]
    if draft.implication_technique:
        lines.append(f"**Implication technique :** {draft.implication_technique}")
    if draft.annule:
        lines.append(f"**Annule :** {draft.annule}")
    if draft.action_de_suivi:
        lines.append(f"**Action de suivi :** {draft.action_de_suivi}")
    return "\n".join(lines) + "\n"


# =============================================================================
# Append à DECISIONS.md
# =============================================================================
_TEMPLATE_HEADER_MARKER = "## Modèle pour les futures décisions"


def append_decision(
    draft: DecisionDraft, *, output_path: Path, today: date | None = None
) -> DecisionWriteResult:
    """Append la décision rendue à ``output_path``.

    Si le fichier existe, insère AVANT la section template (« Modèle
    pour les futures décisions »). Si la section n'existe pas, append
    en fin de fichier. Si le fichier n'existe pas, crée un nouveau
    fichier avec juste la décision (mode test).

    Idempotent par contenu : si une décision avec le même titre existe
    déjà (case-insensitive), on ne réécrit pas.
    """
    today = today or datetime.now(UTC).date()
    existing = output_path.read_text(encoding="utf-8") if output_path.exists() else ""

    title_pattern = re.compile(
        rf"^##\s+D-\d{{3}}\s+—\s+{re.escape(draft.title)}\s*$",
        re.MULTILINE | re.IGNORECASE,
    )
    if title_pattern.search(existing):
        logger.warning(
            f"DecisionLogger — décision '{draft.title}' déjà présente, skip"
        )
        # Récupère l'ID existant
        match = re.search(
            rf"^##\s+(D-\d{{3}})\s+—\s+{re.escape(draft.title)}",
            existing,
            re.MULTILINE | re.IGNORECASE,
        )
        existing_id = match.group(1) if match else "D-???"
        return DecisionWriteResult(
            decision_id=existing_id, path=output_path, appended=False
        )

    next_id = find_next_decision_id(existing)
    block = render_decision(draft, decision_id=next_id, today=today)
    separator = "\n---\n\n"
    insertion = separator + block

    output_path.parent.mkdir(parents=True, exist_ok=True)
    if not existing:
        output_path.write_text(block, encoding="utf-8")
    elif _TEMPLATE_HEADER_MARKER in existing:
        new_content = existing.replace(
            "---\n\n" + _TEMPLATE_HEADER_MARKER,
            insertion.lstrip("\n") + "---\n\n" + _TEMPLATE_HEADER_MARKER,
            1,
        )
        output_path.write_text(new_content, encoding="utf-8")
    else:
        with output_path.open("a", encoding="utf-8") as fh:
            fh.write(insertion)

    return DecisionWriteResult(
        decision_id=next_id, path=output_path, appended=True
    )


# =============================================================================
# Agent
# =============================================================================
class DecisionLogger(BaseAgent):
    """Knowledge Steward — append décisions structurantes à DECISIONS.md."""

    name = "DecisionLogger"
    command = "/log-decision"
    breaker_name = None
    ai_act_risk_class = "minimal"

    def __init__(
        self,
        *,
        output_path: Path | None = None,
    ) -> None:
        # Pas de default vers le vrai DECISIONS.md dans __init__ —
        # ça oblige le caller (slash ou test) à être explicite sur la
        # cible d'écriture.
        self._output_path = output_path

    async def run(self) -> RunResult:
        """Health check passif — vérifie l'accessibilité du fichier cible."""
        path = self._output_path or DEFAULT_DECISIONS_PATH
        exists = path.exists()
        try:
            content = path.read_text(encoding="utf-8") if exists else ""
        except (OSError, UnicodeDecodeError) as exc:
            return RunResult(status="failed", error=f"read {path.name}: {exc}")
        count = len(_DECISION_HEADER_RE.findall(content))
        return RunResult(
            status="success",
            output_summary=f"{count} décisions présentes dans {path.name}",
            extras={"decisions_count": count, "path": str(path)},
        )


__all__ = [
    "DEFAULT_DECISIONS_PATH",
    "DecisionDraft",
    "DecisionLogger",
    "DecisionWriteResult",
    "append_decision",
    "find_next_decision_id",
    "render_decision",
]
