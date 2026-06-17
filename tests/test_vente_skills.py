"""Tests de la banque de skills de l'agent Vente (archi v2, S4)."""

from __future__ import annotations

from pathlib import Path

from argos_ops.poles.vente import skills


def test_real_bank_is_healthy() -> None:
    """La banque committée (data/poles/vente) est saine : parité fiches ↔ pole.yaml."""
    assert skills.validate_skill_bank() == []
    bank = {s.id for s in skills.load_skill_bank()}
    assert "outbound-perso" in bank and "deal-scoring" in bank
    assert len(bank) == 8


def _scaffold(root: Path, *, declared: list[str], fiches: dict[str, str]) -> None:
    d = root / "vente" / "agent" / "skills"
    d.mkdir(parents=True, exist_ok=True)
    skills_yaml = "".join(f"    - {s}\n" for s in declared)
    (root / "vente" / "pole.yaml").write_text(
        "id: vente\nname: Vente\nagent:\n  name: VenteAgent\n  skills:\n"
        + skills_yaml
        + "scripts: []\nreads_cross_pole: []\nfront_tools: [memory_table]\n",
        encoding="utf-8",
    )
    for sid, body in fiches.items():
        (d / f"{sid}.md").write_text(body, encoding="utf-8")


def test_orphan_fiche_flagged(tmp_path: Path) -> None:
    _scaffold(
        tmp_path,
        declared=["a"],
        fiches={
            "a": "---\nid: a\nrole: outreach\n---\nA",
            "b": "---\nid: b\nrole: support\n---\nB",  # pas dans pole.yaml
        },
    )
    issues = skills.validate_skill_bank(poles_root=tmp_path)
    assert any("orpheline" in i.lower() and "b" in i for i in issues)


def test_missing_fiche_flagged(tmp_path: Path) -> None:
    _scaffold(tmp_path, declared=["a", "b"], fiches={"a": "---\nid: a\nrole: outreach\n---\nA"})
    issues = skills.validate_skill_bank(poles_root=tmp_path)
    assert any("sans fiche" in i.lower() and "b" in i for i in issues)


def test_unknown_role_flagged(tmp_path: Path) -> None:
    _scaffold(tmp_path, declared=["a"], fiches={"a": "---\nid: a\nrole: wizardry\n---\nA"})
    issues = skills.validate_skill_bank(poles_root=tmp_path)
    assert any("rôle inconnu" in i.lower() for i in issues)
