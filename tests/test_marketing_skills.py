"""Tests de la banque de skills de l'agent Marketing (archi v2, S2).

Intégration : la banque réelle (12 fiches commitées) doit valider contre
``pole.yaml``. Hermétique : détection des écarts (fiche manquante, orpheline,
writer sans canal).
"""

from __future__ import annotations

from pathlib import Path

from argos_ops.poles.config import POLES_DIR
from argos_ops.poles.marketing.skills import load_skill_bank, skills_dir, validate_skill_bank


def test_real_bank_is_complete_and_valid() -> None:
    bank = load_skill_bank(poles_root=POLES_DIR)
    ids = {s.id for s in bank}
    # Les 6 writers réseaux + SEO/newsletter/reply/editorial/brand-check/kb.
    assert {
        "linkedin-writer",
        "mastodon-writer",
        "meta-writer",
        "x-writer",
        "bluesky-writer",
        "truth-social-writer",
        "seo-brief",
        "newsletter",
        "reply",
        "editorial",
        "brand-check",
        "kb-updater",
    } <= ids
    assert validate_skill_bank(poles_root=POLES_DIR) == []


def _scaffold(root: Path, *, declared: list[str], fiches: dict[str, str]) -> None:
    d = root / "marketing"
    d.mkdir(parents=True, exist_ok=True)
    skills = "\n".join(f"    - {s}" for s in declared)
    (d / "pole.yaml").write_text(
        "id: marketing\nname: Marketing\nagent:\n  name: MarketingAgent\n  skills:\n"
        f"{skills}\nscripts: []\nreads_cross_pole: [veille]\nfront_tools: []\n",
        encoding="utf-8",
    )
    sd = skills_dir(poles_root=root)
    sd.mkdir(parents=True, exist_ok=True)
    for sid, front in fiches.items():
        (sd / f"{sid}.md").write_text(f"---\n{front}---\n\ncorps\n", encoding="utf-8")


def test_missing_fiche_flagged(tmp_path: Path) -> None:
    _scaffold(
        tmp_path,
        declared=["linkedin-writer", "ghost"],
        fiches={"linkedin-writer": "id: linkedin-writer\nrole: writer\nchannel: linkedin\n"},
    )
    issues = validate_skill_bank(poles_root=tmp_path)
    assert any("ghost" in i and "sans fiche" in i for i in issues)


def test_orphan_fiche_and_writer_without_channel(tmp_path: Path) -> None:
    _scaffold(
        tmp_path,
        declared=["linkedin-writer"],
        fiches={
            "linkedin-writer": "id: linkedin-writer\nrole: writer\n",  # writer sans canal
            "orpheline": "id: orpheline\nrole: writer\nchannel: linkedin\n",  # pas déclarée
        },
    )
    issues = validate_skill_bank(poles_root=tmp_path)
    assert any("orpheline" in i for i in issues)
    assert any("linkedin-writer" in i and "canal" in i for i in issues)


def test_load_skill_bank_skips_corrupt_fiche(tmp_path: Path) -> None:
    _scaffold(
        tmp_path,
        declared=["linkedin-writer"],
        fiches={"linkedin-writer": "id: linkedin-writer\nrole: writer\nchannel: linkedin\n"},
    )
    bad = skills_dir(poles_root=tmp_path) / "bad.md"
    bad.write_text("---\nfoo: [unclosed\n---\n\nbody\n", encoding="utf-8")
    bank = load_skill_bank(poles_root=tmp_path)  # best-effort : ignore le fautif
    assert [s.id for s in bank] == ["linkedin-writer"]
