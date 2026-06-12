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


# =============================================================================
# Cerveau (Axe 2) — extraction société + filtre ICP + fichier de revue
# =============================================================================
def _titles() -> list[tuple[ProspectSource, str]]:
    return [
        (ProspectSource.ANNONCES_LEGALES, "Acme SAS — création société (Paris)"),
        (ProspectSource.LINKEDIN_JOBS, "RSSI / CISO H-F — Beta Santé (Lyon)"),
        (ProspectSource.CRUNCHBASE_NEWS, "Weekly funding recap"),
    ]


def test_build_candidates_prompt_indexes_titles_and_guards_injection() -> None:
    from argos_ops.agents.prospect_miner import build_candidates_prompt

    prompt = build_candidates_prompt(_titles())
    assert "index: 0" in prompt and "index: 2" in prompt
    assert "DONNÉE non fiable" in prompt
    assert '"candidates"' in prompt


def test_parse_brain_candidates_keeps_relevant_filters_noise() -> None:
    from argos_ops.agents.prospect_miner import parse_brain_candidates

    titles = _titles()
    data = {
        "candidates": [
            {"index": 0, "company": "Acme SAS", "relevance": "high", "rationale": "création SaaS"},
            {
                "index": 1,
                "company": "Beta Santé",
                "relevance": "medium",
                "rationale": "embauche RSSI",
            },
            {"index": 2, "company": "", "relevance": "low", "rationale": "recap générique"},
            {"index": 99, "company": "Hors batch", "relevance": "high", "rationale": "x"},
            {"index": 0, "company": "X" * 200, "relevance": "high", "rationale": "trop long"},
        ]
    }
    kept, filtered = parse_brain_candidates(data, titles)
    assert [c.company for c in kept] == ["Acme SAS", "Beta Santé"]
    assert kept[0].source == "annonces_legales"
    assert kept[0].raw_signal.startswith("Acme SAS")
    assert filtered == 1  # le low compté comme bruit


def test_extract_candidates_falls_back_to_heuristic(monkeypatch) -> None:
    import asyncio

    from argos_ops.agents import prospect_miner as pm
    from argos_ops.brain import BrainAnswer

    async def fake_think(prompt: str, **_: object) -> BrainAnswer:
        return BrainAnswer(ok=False, data=None, raw=None, engine="disabled", error="off")

    monkeypatch.setattr(pm, "think_json", fake_think)
    kept, filtered, engine = asyncio.run(pm.extract_candidates(_titles()))
    assert engine == "disabled"
    assert filtered == 0
    # Heuristique : split sur le tiret, pas de filtre ICP.
    companies = [c.company for c in kept]
    assert "Acme SAS" in companies
    assert all(c.relevance == "unknown" for c in kept)


def test_persist_candidates_writes_review_yaml(tmp_path: Path) -> None:
    from datetime import date

    import yaml

    from argos_ops.agents.prospect_miner import CompanyCandidate, persist_candidates

    path = persist_candidates(
        [
            CompanyCandidate(
                company="Acme SAS",
                source="annonces_legales",
                raw_signal="Acme SAS — création société",
                relevance="high",
                rationale="création SaaS",
            )
        ],
        candidates_dir=tmp_path,
        day=date(2026, 6, 12),
        engine="claude",
    )
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert raw["extraction_engine"] == "claude"
    assert raw["candidates"][0]["company"] == "Acme SAS"
    assert raw["candidates"][0]["relevance"] == "high"
