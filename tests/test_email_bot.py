"""Tests unitaires de l'EmailBot.

Couvrent le formatting de l'embed Discord et la sérialisation des stats.
La persistance CRM (company/lead/interaction) et l'IMAP/SMTP réel sont
validés en intégration via test live D-005.
"""

from __future__ import annotations

from argos_ops.agents.email_bot import IngestStats, build_inbox_embed
from argos_ops.notifications.discord import GREEN, YELLOW


# =============================================================================
# IngestStats.summary()
# =============================================================================
def test_ingest_stats_summary_format() -> None:
    stats = IngestStats(
        fetched=10, ingested=7, new_leads=3, new_companies=2, skipped_noreply=2, failures=1
    )
    assert stats.summary() == (
        "fetched=10 ingested=7 new_leads=3 new_companies=2 skipped_noreply=2 failures=1"
    )


def test_ingest_stats_default_subjects_is_empty_list() -> None:
    stats = IngestStats()
    assert stats.subjects == []


# =============================================================================
# build_inbox_embed — couleur
# =============================================================================
def test_build_inbox_embed_green_when_empty() -> None:
    embed = build_inbox_embed(IngestStats(fetched=0))
    assert embed.color == GREEN
    assert "Aucun email" in (embed.description or "")


def test_build_inbox_embed_yellow_when_ingested() -> None:
    stats = IngestStats(fetched=3, ingested=3, new_leads=2, new_companies=1)
    embed = build_inbox_embed(stats)
    assert embed.color == YELLOW
    assert "/check-emails" in (embed.description or "")


# =============================================================================
# build_inbox_embed — contenu
# =============================================================================
def test_build_inbox_embed_includes_counts() -> None:
    stats = IngestStats(fetched=5, ingested=4, new_leads=2, skipped_noreply=1, failures=0)
    embed = build_inbox_embed(stats)
    field_map = {f.name: f.value for f in embed.fields}
    assert field_map["Récupérés"] == "5"
    assert field_map["Ingérés"] == "4"
    assert field_map["Nouveaux leads"] == "2"
    assert field_map["Skip noreply"] == "1"
    assert field_map["Échecs"] == "0"


def test_build_inbox_embed_lists_subjects_capped_at_five() -> None:
    stats = IngestStats(
        fetched=8,
        ingested=8,
        subjects=[f"Sujet n°{i}" for i in range(8)],
    )
    embed = build_inbox_embed(stats)
    field_map = {f.name: f.value for f in embed.fields}
    assert "Sujets" in field_map
    sujets_block = field_map["Sujets"]
    assert sujets_block.count("• ") == 5  # 5 lignes max
    assert "+3 autres" in sujets_block


def test_build_inbox_embed_no_subjects_field_when_empty() -> None:
    stats = IngestStats(fetched=0, ingested=0)
    embed = build_inbox_embed(stats)
    field_names = [f.name for f in embed.fields]
    assert "Sujets" not in field_names


def test_build_inbox_embed_truncates_long_subject() -> None:
    long_subject = "X" * 200
    stats = IngestStats(fetched=1, ingested=1, subjects=[long_subject])
    embed = build_inbox_embed(stats)
    field_map = {f.name: f.value for f in embed.fields}
    assert "Sujets" in field_map
    # Le sujet est tronqué à 80 caractères
    assert "X" * 80 in field_map["Sujets"]
    assert "X" * 81 not in field_map["Sujets"]
