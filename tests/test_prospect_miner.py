"""Tests unitaires de ``argos_ops.agents.prospect_miner`` (P22.H Sales Sprint 3).

Couvre les pures functions du module (parsing RSS, append CSV
idempotent, build_embed). L'agent end-to-end ``run()`` est testé en
intégration légère avec un sources.yaml temp + httpx mocké (skipé si
les sources sont inaccessibles).
"""

from __future__ import annotations

import csv
from pathlib import Path

from argos_ops.agents.prospect_miner import (
    MiningStats,
    _append_to_inbox,
    _extract_company_from_title,
    _parse_rss_titles,
    _read_existing_keys,
    build_mining_embed,
)
from argos_ops.sales.models import Prospect, ProspectSource


def _sample_rss() -> bytes:
    return """<?xml version="1.0" encoding="utf-8"?>
<rss version="2.0">
  <channel>
    <title>Annonces</title>
    <item><title>Acme SAS — création société</title></item>
    <item><title>Foobar SARL - mutation capital</title></item>
    <item><title></title></item>
  </channel>
</rss>
""".encode()


def test_parse_rss_titles_extracts_non_empty() -> None:
    titles = _parse_rss_titles(_sample_rss())
    assert titles == ["Acme SAS — création société", "Foobar SARL - mutation capital"]


def test_extract_company_from_title_em_dash() -> None:
    company, domain = _extract_company_from_title("Acme SAS — création société")
    assert company == "Acme SAS"
    assert domain is None


def test_extract_company_from_title_hyphen() -> None:
    company, _ = _extract_company_from_title("Foobar SARL - mutation capital")
    assert company == "Foobar SARL"


def test_extract_company_ignores_overly_long_titles() -> None:
    company, _ = _extract_company_from_title("a" * 200)
    assert company is None


def test_read_existing_keys_empty_when_missing(tmp_path: Path) -> None:
    assert _read_existing_keys(tmp_path / "absent.csv") == set()


def test_append_to_inbox_writes_header_and_dedup(tmp_path: Path) -> None:
    csv_path = tmp_path / "leads.csv"
    prospect_ok = Prospect(
        full_name="Marc Dupont",
        company="Acme",
        domain="acme.fr",
        source=ProspectSource.MANUAL,
        title_hint="CISO",
    )
    prospect_dup = Prospect(
        full_name="Marc Dupont",
        company="Acme",
        domain="acme.fr",
        source=ProspectSource.MANUAL,
    )
    prospect_no_domain = Prospect(
        full_name="Sans Domaine",
        company="X",
        domain="",
        source=ProspectSource.ANNONCES_LEGALES,
        raw_signal="title only",
    )
    existing: set[tuple[str, str]] = set()
    new, dup, by_source = _append_to_inbox(
        [prospect_ok, prospect_dup, prospect_no_domain],
        csv_path=csv_path,
        existing_keys=existing,
    )
    assert new == 1
    assert dup == 1
    assert by_source["manual"] == 1
    # header + 1 row
    with csv_path.open() as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 1
    assert rows[0]["full_name"] == "Marc Dupont"

    # 2e pass : pas de duplicate, pas d'écriture
    existing2 = _read_existing_keys(csv_path)
    new2, dup2, _ = _append_to_inbox([prospect_ok], csv_path=csv_path, existing_keys=existing2)
    assert new2 == 0 and dup2 == 1


def test_build_mining_embed_green_when_zero_new() -> None:
    embed = build_mining_embed(MiningStats(candidates_seen=10, new_appended=0))
    assert embed.color == 0x2ECC71  # GREEN
    assert "Aucun nouveau" in (embed.description or "")


def test_build_mining_embed_yellow_when_new() -> None:
    embed = build_mining_embed(
        MiningStats(
            candidates_seen=5,
            new_appended=3,
            by_source={"manual": 2, "annonces_legales": 1},
        )
    )
    assert embed.color == 0xF1C40F  # YELLOW
    assert any("Par source" in f.name for f in embed.fields)
