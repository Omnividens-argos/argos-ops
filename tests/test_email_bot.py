"""Tests unitaires de l'EmailBot.

Couvrent le formatting de l'embed Discord, la sérialisation des stats et
les faits mémoire de flotte (build_lead_facts). La persistance CRM
(company/lead/interaction) et l'IMAP/SMTP réel sont validés en
intégration via test live D-005.
"""

from __future__ import annotations

from argos_ops.agents.email_bot import IngestStats, build_inbox_embed, build_lead_facts
from argos_ops.integrations.zimbra import EmailMessage
from argos_ops.notifications.discord import GREEN, YELLOW


def _msg(email: str, name: str | None = None, subject: str = "Demande de devis") -> EmailMessage:
    return EmailMessage(
        uid="1",
        from_email=email,
        from_name=name,
        to=["contact@omnividens.fr"],
        subject=subject,
        body_text="corps",
        body_html=None,
        date=None,
        message_id=None,
        in_reply_to=None,
        references=None,
    )


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


# =============================================================================
# build_lead_facts — mémoire de flotte
# =============================================================================
def test_build_lead_facts_one_per_new_lead() -> None:
    facts = build_lead_facts([_msg("marc@acme.fr", "Marc D."), _msg("sara@beta.io")])
    assert len(facts) == 2
    first = facts[0]
    assert first["kind"] == "lead-signal"
    assert "Marc D. <marc@acme.fr>" in first["body"]
    assert "Demande de devis" in first["body"]
    assert first["ttl_days"] == 90
    assert "inbound" in (first.get("tags") or [])


def test_build_lead_facts_capped_at_five() -> None:
    msgs = [_msg(f"lead{i}@corp.fr") for i in range(8)]
    assert len(build_lead_facts(msgs)) == 5


def test_build_lead_facts_empty_when_no_new_lead() -> None:
    assert build_lead_facts([]) == []
