"""Tests de la banque de skills de l'agent Pub (archi v2, S3)."""

from __future__ import annotations

from pathlib import Path

from argos_ops.poles.pub import skills


def _scaffold(root: Path, *, declared: list[str], cards: dict[str, str]) -> None:
    pub = root / "pub"
    (pub / "agent" / "skills").mkdir(parents=True, exist_ok=True)
    skills_yaml = "".join(f"    - {s}\n" for s in declared)
    (pub / "pole.yaml").write_text(
        "id: pub\nname: Pub\nagent:\n  name: PubAgent\n  skills:\n"
        + skills_yaml
        + "scripts: []\nreads_cross_pole: [veille]\nfront_tools: [memory_table]\n",
        encoding="utf-8",
    )
    for skill_id, body in cards.items():
        (pub / "agent" / "skills" / f"{skill_id}.md").write_text(body, encoding="utf-8")


def test_load_and_validate_healthy_bank(tmp_path: Path) -> None:
    _scaffold(
        tmp_path,
        declared=["ads-creative", "ads-optimizer"],
        cards={
            "ads-creative": "---\nid: ads-creative\nrole: creative\n---\n\nGénère 3 variantes.",
            "ads-optimizer": "---\nid: ads-optimizer\nrole: optimizer\n---\n\nAnalyse un CSV.",
        },
    )
    bank = skills.load_skill_bank(poles_root=tmp_path)
    assert {s.id for s in bank} == {"ads-creative", "ads-optimizer"}
    assert skills.validate_skill_bank(poles_root=tmp_path) == []


def test_validate_flags_missing_card(tmp_path: Path) -> None:
    _scaffold(
        tmp_path,
        declared=["ads-creative", "ads-optimizer"],
        cards={"ads-creative": "---\nid: ads-creative\nrole: creative\n---\n\nx"},
    )
    issues = skills.validate_skill_bank(poles_root=tmp_path)
    assert any("ads-optimizer" in i and "sans fiche" in i for i in issues)


def test_validate_flags_orphan_and_unknown_role(tmp_path: Path) -> None:
    _scaffold(
        tmp_path,
        declared=["ads-creative"],
        cards={
            "ads-creative": "---\nid: ads-creative\nrole: bogus\n---\n\nx",
            "ads-orphan": "---\nid: ads-orphan\nrole: creative\n---\n\ny",
        },
    )
    issues = skills.validate_skill_bank(poles_root=tmp_path)
    assert any("orpheline" in i for i in issues)
    assert any("Rôle inconnu" in i for i in issues)
