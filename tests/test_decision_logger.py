"""Tests unitaires de :mod:`argos_ops.agents.decision_logger` (P22.E).

GARDE-FOU : tous les tests passent un ``output_path`` dans ``tmp_path``.
Aucun test ne doit jamais écrire le vrai ``docs/DECISIONS.md``.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from argos_ops.agents.decision_logger import (
    DecisionDraft,
    append_decision,
    find_next_decision_id,
    render_decision,
)


# =============================================================================
# find_next_decision_id
# =============================================================================
def test_find_next_decision_id_empty() -> None:
    assert find_next_decision_id("") == "D-001"


def test_find_next_decision_id_increments() -> None:
    md = "## D-001 — A\n\n## D-002 — B\n\n## D-022 — Reddit\n"
    assert find_next_decision_id(md) == "D-023"


def test_find_next_decision_id_ignores_text_mentions() -> None:
    # « voir D-005 » dans une description ne doit pas compter
    md = "Voir D-005 pour le contexte\n\n## D-010 — Real entry\n"
    assert find_next_decision_id(md) == "D-011"


# =============================================================================
# render_decision
# =============================================================================
def test_render_decision_complete() -> None:
    draft = DecisionDraft(
        title="Test décision",
        partie="P22.E",
        decision="On fait X",
        pourquoi="Parce que Y",
        implication_technique="Z",
        annule="[D-005](#d-005)",
        action_de_suivi="Faire W",
    )
    body = render_decision(draft, decision_id="D-024", today=date(2026, 5, 23))
    assert "## D-024 — Test décision" in body
    assert "**Date :** 2026-05-23" in body
    assert "**Partie :** P22.E" in body
    assert "**Décision :** On fait X" in body
    assert "**Pourquoi :** Parce que Y" in body
    assert "**Implication technique :** Z" in body
    assert "**Annule :** [D-005](#d-005)" in body
    assert "**Action de suivi :** Faire W" in body


def test_render_decision_optional_fields() -> None:
    draft = DecisionDraft(
        title="Minimal", partie="P22.E", decision="X", pourquoi="Y"
    )
    body = render_decision(draft, decision_id="D-001", today=date(2026, 5, 23))
    assert "Implication technique" not in body
    assert "Annule" not in body
    assert "Action de suivi" not in body


# =============================================================================
# append_decision — toujours tmp_path
# =============================================================================
def test_append_decision_creates_new_file(tmp_path: Path) -> None:
    out = tmp_path / "DECISIONS.md"
    draft = DecisionDraft(title="x", partie="P", decision="d", pourquoi="p")
    result = append_decision(draft, output_path=out, today=date(2026, 5, 23))
    assert result.appended is True
    assert result.decision_id == "D-001"
    assert "## D-001 — x" in out.read_text(encoding="utf-8")


def test_append_decision_inserts_before_template_section(tmp_path: Path) -> None:
    out = tmp_path / "DECISIONS.md"
    out.write_text(
        "## D-001 — Existing\nbody\n\n---\n\n## Modèle pour les futures décisions\n\nTemplate\n",
        encoding="utf-8",
    )
    draft = DecisionDraft(title="new", partie="P", decision="d", pourquoi="p")
    append_decision(draft, output_path=out, today=date(2026, 5, 23))
    content = out.read_text(encoding="utf-8")
    assert content.index("## D-002 — new") < content.index("## Modèle pour les futures décisions")


def test_append_decision_idempotent_by_title(tmp_path: Path) -> None:
    out = tmp_path / "DECISIONS.md"
    draft = DecisionDraft(title="dup", partie="P", decision="d", pourquoi="p")
    first = append_decision(draft, output_path=out, today=date(2026, 5, 23))
    second = append_decision(draft, output_path=out, today=date(2026, 5, 23))
    assert first.appended is True
    assert second.appended is False
    # Le fichier ne doit contenir qu'une seule occurrence
    content = out.read_text(encoding="utf-8")
    assert content.count("## D-001 — dup") == 1
