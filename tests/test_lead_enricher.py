"""Tests unitaires de ``argos_ops.agents.lead_enricher`` (P22.H)."""

from __future__ import annotations

from pathlib import Path

from argos_ops.agents.lead_enricher import (
    EnrichmentStats,
    _write_enriched_md,
    build_enrichment_embed,
)
from argos_ops.sales.enrichment import enrich_lead


def test_write_enriched_md_creates_frontmatter_and_sections(tmp_path: Path) -> None:
    payload = enrich_lead(
        full_name="Marc Dupont",
        domain="acme.fr",
        title_hint="CISO",
        company_size_hint=120,
        has_recent_breach=True,
    )
    out = tmp_path / "marc-dupont-acme-fr.md"
    _write_enriched_md(out, full_name="Marc Dupont", domain="acme.fr", enriched=payload)
    content = out.read_text(encoding="utf-8")
    assert content.startswith("---\n")
    assert "full_name: Marc Dupont" in content
    assert "## BANT" in content
    assert "## Persona" in content
    assert "## Candidats email" in content
    assert "marc.dupont@acme.fr" in content


def test_enrichment_embed_green_if_no_new() -> None:
    embed = build_enrichment_embed(
        EnrichmentStats(leads_seen=5, newly_enriched=0, already_enriched=5)
    )
    assert embed.color == 0x2ECC71


def test_enrichment_embed_yellow_if_new() -> None:
    stats = EnrichmentStats(
        leads_seen=10,
        newly_enriched=3,
        qualified=2,
        new_slugs=["a", "b", "c"],
    )
    embed = build_enrichment_embed(stats)
    assert embed.color == 0xF1C40F
    assert any("Qualifiés" in f.name for f in embed.fields)
