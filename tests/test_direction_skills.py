"""Tests de la banque de skills de l'agent Direction (archi v2, S6) — hermétiques.

Scaffold un ``pole.yaml`` direction sous ``tmp_path`` déclarant les 9 skills + des
fiches markdown correspondantes, puis audite la parité fiches ↔ pole.yaml et les
rôles connus. Miroir de ``tests/test_finance_skills.py``.
"""

from __future__ import annotations

from pathlib import Path

from argos_ops.poles.direction.skills import (
    KNOWN_ROLES,
    load_skill_bank,
    validate_skill_bank,
)

# Les 9 skills de l'agent Direction → leur rôle (parmi KNOWN_ROLES).
_SKILLS: dict[str, str] = {
    "release-notes": "reporting",
    "weekly-synthesis": "reporting",
    "okr-review": "strategy",
    "board-pack": "reporting",
    "decision-log": "governance",
    "changelog": "reporting",
    "roadmap-publish": "product",
    "feedback-arbitrage": "product",
    "bug-triage": "product",
}


def _pole_yaml(root: Path, skill_ids: list[str]) -> None:
    """Écrit ``data/poles/direction/pole.yaml`` déclarant ``skill_ids`` sous agent.skills."""
    skills_block = "\n".join(f"    - {sid}" for sid in skill_ids)
    body = (
        "id: direction\n"
        "name: Direction\n"
        "description: Pilotage transversal.\n"
        "agent:\n"
        "  name: DirectionAgent\n"
        "  trigger: cron\n"
        "  skills:\n"
        f"{skills_block}\n"
    )
    path = root / "direction" / "pole.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


def _skill_card(root: Path, skill_id: str, role: str) -> None:
    """Écrit une fiche ``agent/skills/<id>.md`` avec frontmatter id + role + un corps."""
    card = (
        "---\n"
        f"id: {skill_id}\n"
        f"role: {role}\n"
        "---\n"
        "\n"
        f"Skill de pilotage Direction « {skill_id} » (rôle {role}).\n"
    )
    path = root / "direction" / "agent" / "skills" / f"{skill_id}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(card, encoding="utf-8")


def _scaffold_sane(root: Path) -> None:
    """Scaffold une banque saine : 9 skills déclarés + 9 fiches assorties."""
    _pole_yaml(root, list(_SKILLS))
    for sid, role in _SKILLS.items():
        _skill_card(root, sid, role)


def test_known_roles() -> None:
    assert {"reporting", "strategy", "product", "governance"} == KNOWN_ROLES


def test_sane_bank_loads_nine_and_validates(tmp_path: Path) -> None:
    _scaffold_sane(tmp_path)
    bank = load_skill_bank(poles_root=tmp_path)
    assert len(bank) == 9
    assert {s.id for s in bank} == set(_SKILLS)
    assert all(s.role in KNOWN_ROLES for s in bank)
    assert all(s.summary for s in bank)  # corps non vide
    assert validate_skill_bank(poles_root=tmp_path) == []


def test_missing_card_flagged(tmp_path: Path) -> None:
    _scaffold_sane(tmp_path)
    # Supprime la fiche d'un skill déclaré → « déclaré sans fiche ».
    (tmp_path / "direction" / "agent" / "skills" / "bug-triage.md").unlink()
    issues = validate_skill_bank(poles_root=tmp_path)
    assert any("déclaré sans fiche" in i and "bug-triage" in i for i in issues)


def test_orphan_card_flagged(tmp_path: Path) -> None:
    _scaffold_sane(tmp_path)
    # Ajoute une fiche non déclarée dans pole.yaml → « orpheline ».
    _skill_card(tmp_path, "ghost-skill", "reporting")
    issues = validate_skill_bank(poles_root=tmp_path)
    assert any("orpheline" in i and "ghost-skill" in i for i in issues)


def test_unknown_role_flagged(tmp_path: Path) -> None:
    # Déclare un skill avec un rôle hors KNOWN_ROLES.
    _pole_yaml(tmp_path, ["release-notes", "bizarre-skill"])
    _skill_card(tmp_path, "release-notes", "reporting")
    _skill_card(tmp_path, "bizarre-skill", "wizardry")  # rôle inconnu
    issues = validate_skill_bank(poles_root=tmp_path)
    assert any("Rôle inconnu" in i and "bizarre-skill" in i for i in issues)
