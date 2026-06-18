"""Tests de la charte / ton du pôle Marketing (archi v2, S2)."""

from __future__ import annotations

from pathlib import Path

from argos_ops.poles.marketing.charter import Charter, brand_check, load_charter, save_charter


def test_load_default_when_absent(tmp_path: Path) -> None:
    c = load_charter(poles_root=tmp_path)
    assert c.domain == "omnividens.fr"
    assert "on scanne" in c.tagline


def test_save_load_roundtrip(tmp_path: Path) -> None:
    c = Charter(
        tagline="Test tagline",
        domain="omnividens.fr",
        voice="ton test",
        principles=("p1", "p2"),
        avoid=("a1",),
        banned_terms=("peur",),
        ai_disclosure="IA assistée",
    )
    save_charter(c, poles_root=tmp_path)
    loaded = load_charter(poles_root=tmp_path)
    assert loaded.tagline == "Test tagline"
    assert loaded.principles == ("p1", "p2")
    assert loaded.banned_terms == ("peur",)


def test_brand_check_flags_fud_and_wrong_domain() -> None:
    issues = brand_check("Une catastrophe inviolable, rendez-vous sur omnividens.com", Charter())
    assert any("catastrophe" in i for i in issues)
    assert any("omnividens.com" in i for i in issues)


def test_brand_check_clean_text_passes() -> None:
    issues = brand_check(
        "On scanne votre exposition et on priorise. Détails sur omnividens.fr", Charter()
    )
    assert issues == []


def test_brand_check_multiword_and_mixed_case() -> None:
    # Terme banni multi-mots + casse mixte (détection insensible à la casse).
    issues = brand_check("Une GARANTIE TOTALE et un site 100% Sécurisé", Charter())
    assert len(issues) >= 2


def test_brand_check_detects_non_com_wrong_tld() -> None:
    # Robustesse : .io / .net aussi flaggés, pas seulement .com.
    assert brand_check("Voir omnividens.io", Charter())
    assert brand_check("Voir omnividens.net pour plus", Charter())


def test_brand_check_no_false_positive_on_community() -> None:
    # « omnividens.community » ne doit PAS matcher comme « .com ».
    assert brand_check("Rejoignez omnividens.community sur le forum", Charter()) == []


def test_load_charter_corrupt_yaml_falls_back_to_defaults(tmp_path: Path) -> None:
    (tmp_path / "marketing").mkdir(parents=True)
    (tmp_path / "marketing" / "charter.yaml").write_text("tagline: [unclosed", encoding="utf-8")
    c = load_charter(poles_root=tmp_path)
    assert c.domain == "omnividens.fr"  # défauts


def test_load_charter_non_dict_falls_back_to_defaults(tmp_path: Path) -> None:
    (tmp_path / "marketing").mkdir(parents=True)
    (tmp_path / "marketing" / "charter.yaml").write_text("- une\n- liste\n", encoding="utf-8")
    c = load_charter(poles_root=tmp_path)
    assert c.tagline == Charter().tagline
