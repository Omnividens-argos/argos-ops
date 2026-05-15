"""Tests unitaires du module ``argos_ops.outbound`` (P13.A shadow).

Couvre :

- ``templates.py`` : slugify, opt-out HMAC, footer rendering, cadence
- ``sequence.py`` : parsing CSV, scaffold idempotent, load_sequence_state
- ``models.py`` : enum TouchStep + dataclasses (smoke tests)

Pas de test DB ni de notif Discord ici — ces aspects sont couverts via
``test_outbound_bot.py`` (agent end-to-end avec mocks).
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
import yaml

from argos_ops.outbound import (
    LeadInput,
    SequenceState,
    TouchStep,
    build_footer,
    build_opt_out_url,
    compute_touch_dates,
    generate_opt_out_token,
    is_sequence_scaffolded,
    load_sequence_state,
    read_inbox_csv,
    scaffold_sequence_dir,
    slugify,
    verify_opt_out_token,
)
from argos_ops.outbound.templates import OPT_OUT_BASE_URL, TOUCH_CADENCE_DAYS

SECRET = "test-secret-do-not-use-in-prod-32-bytes-min"


# =============================================================================
# slugify
# =============================================================================
def test_slugify_basic() -> None:
    assert slugify("Marc Dupont", "acme.fr") == "marc-dupont-acme-fr"


def test_slugify_handles_accents_and_special_chars() -> None:
    slug = slugify("Sarah Côté-Martin", "tech-start.io")
    # Les accents sont retirés (pas dans [a-z0-9-]), résultat reste utilisable
    assert "sarah" in slug and "martin" in slug and "tech-start-io" in slug
    assert all(c.islower() or c == "-" or c.isdigit() for c in slug)


def test_slugify_idempotent() -> None:
    slug = slugify("Marc Dupont", "acme.fr")
    # Re-slugger ne doit pas mutiler
    assert slugify(slug, "x.fr").startswith("marc-dupont-acme-fr")


def test_slugify_truncates_to_50_chars() -> None:
    huge_name = "A" * 100
    slug = slugify(huge_name, "supercalifragilistic-domain.example.com")
    assert len(slug) <= 50


# =============================================================================
# Cadence
# =============================================================================
def test_compute_touch_dates_returns_5_dates() -> None:
    start = date(2026, 5, 15)
    dates = compute_touch_dates(start)
    assert len(dates) == 5
    assert dates[0] == start
    assert dates[1] == date(2026, 5, 18)  # D+3
    assert dates[2] == date(2026, 5, 22)  # D+7
    assert dates[3] == date(2026, 5, 29)  # D+14
    assert dates[4] == date(2026, 6, 14)  # D+30


def test_touch_cadence_constant_is_5_steps() -> None:
    assert len(TOUCH_CADENCE_DAYS) == 5
    assert TOUCH_CADENCE_DAYS == [0, 3, 7, 14, 30]


# =============================================================================
# Opt-out HMAC
# =============================================================================
def test_opt_out_token_is_16_chars_hex() -> None:
    token = generate_opt_out_token("marc.dupont@acme.fr", SECRET)
    assert len(token) == 16
    assert all(c in "0123456789abcdef" for c in token)


def test_opt_out_token_deterministic_same_email_same_secret() -> None:
    t1 = generate_opt_out_token("marc.dupont@acme.fr", SECRET)
    t2 = generate_opt_out_token("marc.dupont@acme.fr", SECRET)
    assert t1 == t2


def test_opt_out_token_differs_with_email() -> None:
    t1 = generate_opt_out_token("a@acme.fr", SECRET)
    t2 = generate_opt_out_token("b@acme.fr", SECRET)
    assert t1 != t2


def test_opt_out_token_differs_with_secret() -> None:
    t1 = generate_opt_out_token("a@acme.fr", SECRET)
    t2 = generate_opt_out_token("a@acme.fr", "other-secret")
    assert t1 != t2


def test_opt_out_token_email_normalized_lowercase() -> None:
    # Robustesse aux variations de casse côté destinataire
    t1 = generate_opt_out_token("Marc.DUPONT@Acme.FR", SECRET)
    t2 = generate_opt_out_token("marc.dupont@acme.fr", SECRET)
    assert t1 == t2


def test_verify_opt_out_token_accepts_valid() -> None:
    email = "marc@acme.fr"
    token = generate_opt_out_token(email, SECRET)
    assert verify_opt_out_token(email, token, SECRET) is True


def test_verify_opt_out_token_rejects_invalid() -> None:
    assert verify_opt_out_token("marc@acme.fr", "deadbeefdeadbeef", SECRET) is False


def test_verify_opt_out_token_rejects_wrong_secret() -> None:
    token = generate_opt_out_token("marc@acme.fr", SECRET)
    assert verify_opt_out_token("marc@acme.fr", token, "other-secret") is False


def test_build_opt_out_url_format() -> None:
    url = build_opt_out_url("marc@acme.fr", SECRET)
    assert url.startswith(OPT_OUT_BASE_URL + "?")
    assert "email=marc%40acme.fr" in url
    assert "t=" in url


# =============================================================================
# Footer
# =============================================================================
def test_build_footer_contains_all_required_elements() -> None:
    footer = build_footer(
        email="marc@acme.fr",
        secret=SECRET,
        tagline="Argos — on scanne, vous corrigez.",
        site_url="https://omnividens.fr",
        ai_disclosure="Email rédigé par notre assistant Argos Ops.",
    )
    # AI Act disclosure
    assert "assistant Argos Ops" in footer
    # Tagline
    assert "Argos — on scanne, vous corrigez." in footer
    # Site URL
    assert "https://omnividens.fr" in footer
    # RGPD mention
    assert "intérêt légitime" in footer
    # Opt-out link
    assert "unsubscribe" in footer
    assert "email=marc%40acme.fr" in footer


# =============================================================================
# CSV parsing
# =============================================================================
def test_read_inbox_csv_minimal(tmp_path: Path) -> None:
    csv_path = tmp_path / "leads.csv"
    csv_path.write_text(
        "full_name,domain\nMarc Dupont,acme.fr\nSarah Martin,techstart.io\n",
        encoding="utf-8",
    )
    leads = read_inbox_csv(csv_path)
    assert len(leads) == 2
    assert leads[0].full_name == "Marc Dupont"
    assert leads[0].domain == "acme.fr"
    assert leads[0].title_hint is None
    assert leads[1].domain == "techstart.io"


def test_read_inbox_csv_with_optional_columns(tmp_path: Path) -> None:
    csv_path = tmp_path / "leads.csv"
    csv_path.write_text(
        "full_name,domain,title_hint,linkedin_url\n"
        "Marc Dupont,acme.fr,RSSI,https://linkedin.com/in/marc\n",
        encoding="utf-8",
    )
    leads = read_inbox_csv(csv_path)
    assert leads[0].title_hint == "RSSI"
    assert leads[0].linkedin_url == "https://linkedin.com/in/marc"


def test_read_inbox_csv_ignores_commented_lines(tmp_path: Path) -> None:
    csv_path = tmp_path / "leads.csv"
    csv_path.write_text(
        "full_name,domain\n# commentaire ignoré,foo.fr\nMarc,acme.fr\n",
        encoding="utf-8",
    )
    leads = read_inbox_csv(csv_path)
    assert len(leads) == 1
    assert leads[0].full_name == "Marc"


def test_read_inbox_csv_rejects_invalid_domain(tmp_path: Path) -> None:
    csv_path = tmp_path / "leads.csv"
    csv_path.write_text(
        "full_name,domain\nMarc,not_a_domain\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="invalide"):
        read_inbox_csv(csv_path)


def test_read_inbox_csv_rejects_missing_required_column(tmp_path: Path) -> None:
    csv_path = tmp_path / "leads.csv"
    csv_path.write_text("full_name\nMarc\n", encoding="utf-8")
    with pytest.raises(ValueError, match="colonnes manquantes"):
        read_inbox_csv(csv_path)


def test_read_inbox_csv_rejects_unknown_column(tmp_path: Path) -> None:
    csv_path = tmp_path / "leads.csv"
    csv_path.write_text(
        "full_name,domain,bogus_col\nMarc,acme.fr,x\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="colonnes inconnues"):
        read_inbox_csv(csv_path)


def test_read_inbox_csv_raises_when_file_missing(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        read_inbox_csv(tmp_path / "nope.csv")


# =============================================================================
# Scaffold
# =============================================================================
def test_scaffold_creates_meta_and_5_touch_files(tmp_path: Path) -> None:
    lead = LeadInput(full_name="Marc Dupont", domain="acme.fr", title_hint="RSSI")
    seq_dir = scaffold_sequence_dir(
        lead,
        secret=SECRET,
        start_date=date(2026, 5, 15),
        root=tmp_path,
        enriched_root=tmp_path / "enriched",
    )
    assert seq_dir.name == "marc-dupont-acme-fr"
    assert (seq_dir / "meta.yaml").exists()
    for step in range(1, 6):
        touch_file = seq_dir / f"touch_{step}.md"
        assert touch_file.exists()
        content = touch_file.read_text(encoding="utf-8")
        assert "status: scaffold" in content
        assert f"step: {step}" in content


def test_scaffold_is_idempotent(tmp_path: Path) -> None:
    lead = LeadInput(full_name="Marc Dupont", domain="acme.fr")
    seq_dir_1 = scaffold_sequence_dir(
        lead, secret=SECRET, root=tmp_path, enriched_root=tmp_path / "enriched"
    )
    # Modifie le contenu, puis re-scaffold — le contenu ne doit pas être écrasé
    (seq_dir_1 / "touch_1.md").write_text("CUSTOM_CONTENT", encoding="utf-8")
    seq_dir_2 = scaffold_sequence_dir(
        lead, secret=SECRET, root=tmp_path, enriched_root=tmp_path / "enriched"
    )
    assert seq_dir_1 == seq_dir_2
    assert (seq_dir_2 / "touch_1.md").read_text(encoding="utf-8") == "CUSTOM_CONTENT"


def test_scaffold_meta_yaml_is_valid_and_complete(tmp_path: Path) -> None:
    lead = LeadInput(full_name="Marc Dupont", domain="acme.fr")
    seq_dir = scaffold_sequence_dir(
        lead, secret=SECRET, root=tmp_path, enriched_root=tmp_path / "enriched"
    )
    meta = yaml.safe_load((seq_dir / "meta.yaml").read_text(encoding="utf-8"))
    assert meta["lead_slug"] == "marc-dupont-acme-fr"
    assert meta["full_name"] == "Marc Dupont"
    assert meta["domain"] == "acme.fr"
    assert meta["sequence_status"] == "scaffold"
    assert len(meta["touches"]) == 5
    assert len(meta["opt_out_token"]) == 16
    assert all(t["status"] == "scaffold" for t in meta["touches"])
    assert all(t["body"] is None for t in meta["touches"])


def test_is_sequence_scaffolded_detects_existing(tmp_path: Path) -> None:
    lead = LeadInput(full_name="Marc Dupont", domain="acme.fr")
    slug = slugify(lead.full_name, lead.domain)
    assert is_sequence_scaffolded(slug, root=tmp_path) is False
    scaffold_sequence_dir(lead, secret=SECRET, root=tmp_path, enriched_root=tmp_path / "enriched")
    assert is_sequence_scaffolded(slug, root=tmp_path) is True


def test_load_sequence_state_roundtrip(tmp_path: Path) -> None:
    lead = LeadInput(full_name="Marc Dupont", domain="acme.fr")
    scaffold_sequence_dir(
        lead,
        secret=SECRET,
        start_date=date(2026, 5, 15),
        root=tmp_path,
        enriched_root=tmp_path / "enriched",
    )
    state = load_sequence_state("marc-dupont-acme-fr", root=tmp_path)
    assert isinstance(state, SequenceState)
    assert state.full_name == "Marc Dupont"
    assert state.sequence_status == "scaffold"
    assert len(state.touches) == 5
    assert state.touches[0].step == TouchStep.DISCOVERY
    assert state.touches[0].scheduled_date == date(2026, 5, 15)
    assert state.touches[4].step == TouchStep.BREAKUP
    assert state.touches[4].scheduled_date == date(2026, 6, 14)


def test_load_sequence_state_raises_when_missing(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_sequence_state("ghost-slug-nowhere", root=tmp_path)
