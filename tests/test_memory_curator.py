"""Tests du MemoryCurator — concierge de la mémoire de flotte (P20)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from argos_ops.agents.memory_curator import MemoryCurator, build_report, plan_for_bot
from argos_ops.fleet_memory import Fact, append_fact, archive_fact, read_memory

NOW = datetime(2026, 6, 7, 12, 0, tzinfo=UTC)


def _fact(
    fid: str,
    *,
    status: str = "active",
    ttl_days: int | None = None,
    age_days: int = 0,
    archived_age_days: int | None = None,
    pinned: bool = False,
) -> Fact:
    return Fact(
        id=fid,
        bot="TrendSpotter",
        kind="trend",
        body=f"fait {fid}",
        ttl_days=ttl_days,
        status=status,  # type: ignore[arg-type]
        created_at=NOW - timedelta(days=age_days),
        archived_at=(NOW - timedelta(days=archived_age_days))
        if archived_age_days is not None
        else None,
        pinned=pinned,
    )


# =============================================================================
# plan_for_bot — décision pure
# =============================================================================
def test_ttl_expired_active_is_archived() -> None:
    facts = [_fact("a", ttl_days=21, age_days=30)]
    to_archive, to_delete, _ = plan_for_bot(facts, now=NOW)
    assert to_archive == ["a"]
    assert to_delete == []


def test_ttl_not_expired_is_kept() -> None:
    facts = [_fact("a", ttl_days=21, age_days=5)]
    to_archive, _, _ = plan_for_bot(facts, now=NOW)
    assert to_archive == []


def test_stale_active_without_ttl_is_archived() -> None:
    facts = [_fact("a", age_days=400)]
    to_archive, _, _ = plan_for_bot(facts, now=NOW, stale_active_days=365)
    assert to_archive == ["a"]


def test_stale_disabled_keeps_old_active() -> None:
    facts = [_fact("a", age_days=400)]
    to_archive, _, _ = plan_for_bot(facts, now=NOW, stale_active_days=None)
    assert to_archive == []


def test_archived_long_ago_is_purged() -> None:
    facts = [_fact("a", status="archived", archived_age_days=100)]
    to_archive, to_delete, _ = plan_for_bot(facts, now=NOW, purge_archived_days=90)
    assert to_delete == ["a"]
    assert to_archive == []


def test_archived_recent_is_kept() -> None:
    facts = [_fact("a", status="archived", archived_age_days=10)]
    _, to_delete, _ = plan_for_bot(facts, now=NOW, purge_archived_days=90)
    assert to_delete == []


def test_pinned_is_never_touched() -> None:
    facts = [
        _fact("expired", ttl_days=1, age_days=999, pinned=True),
        _fact("stale", age_days=999, pinned=True),
        _fact("archived", status="archived", archived_age_days=999, pinned=True),
    ]
    to_archive, to_delete, pinned_kept = plan_for_bot(facts, now=NOW)
    assert to_archive == []
    assert to_delete == []
    assert pinned_kept == 3


def test_purge_disabled_keeps_old_archived() -> None:
    facts = [_fact("a", status="archived", archived_age_days=999)]
    _, to_delete, _ = plan_for_bot(facts, now=NOW, purge_archived_days=None)
    assert to_delete == []


# =============================================================================
# build_report
# =============================================================================
def test_report_silent_when_nothing_changed() -> None:
    report = build_report([], [], pinned_kept=2, scanned=5)
    assert report.should_alert is False


def test_report_alerts_when_actions() -> None:
    report = build_report([("TrendSpotter", "a")], [], pinned_kept=0, scanned=3)
    assert report.should_alert is True


# =============================================================================
# curate() — intégration sur tmp_path
# =============================================================================
@pytest.mark.asyncio
async def test_curate_applies_lifecycle(tmp_path: Path) -> None:
    # actif TTL expiré → doit être archivé
    await append_fact(
        "TrendSpotter",
        "sujet expiré",
        kind="trend",
        ttl_days=21,
        created_at=NOW - timedelta(days=30),
        root=tmp_path,
    )
    # actif récent → conservé
    await append_fact(
        "TrendSpotter",
        "sujet récent",
        kind="trend",
        ttl_days=21,
        created_at=NOW - timedelta(days=2),
        root=tmp_path,
    )
    # important (pinned) très vieux → protégé
    await append_fact(
        "TrendSpotter",
        "fait important",
        kind="insight",
        pinned=True,
        created_at=NOW - timedelta(days=999),
        root=tmp_path,
    )
    # déjà archivé depuis longtemps → purge dure
    old = await append_fact("LeadEnricher", "vieux truc", kind="note", root=tmp_path)
    await archive_fact("LeadEnricher", old.id, archived_at=NOW - timedelta(days=120), root=tmp_path)

    curator = MemoryCurator(root=tmp_path)
    report = await curator.curate(now=NOW)

    assert ("TrendSpotter", _id("sujet expiré")) in report.archived
    assert ("LeadEnricher", old.id) in report.deleted
    assert report.pinned_kept == 1

    # Vérifs disque : expiré archivé (exclu de l'actif), important toujours actif,
    # vieux supprimé pour de bon.
    ts_active = {f.body for f in (await read_memory("TrendSpotter", root=tmp_path)).facts}
    assert "sujet récent" in ts_active
    assert "fait important" in ts_active
    assert "sujet expiré" not in ts_active
    assert not (tmp_path / "LeadEnricher" / "facts" / f"{old.id}.md").exists()


def _id(body: str) -> str:
    from argos_ops.fleet_memory import compute_fact_id

    return compute_fact_id(body)
