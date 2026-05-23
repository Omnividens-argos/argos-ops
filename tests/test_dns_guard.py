"""Tests unitaires de :mod:`argos_ops.agents.dns_guard` (P22.D).

Couvre la logique pure : diff de snapshots, classification, embed.
Pas de résolution DNS réelle (``resolve_records`` n'est pas testé ici
— c'est de l'I/O réseau).
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from argos_ops.agents.dns_guard import (
    DnsSnapshot,
    build_dns_embed,
    build_report,
    classify_changes,
    diff_snapshots,
    load_previous,
    save_snapshot,
)
from argos_ops.notifications.discord import GREEN, RED, YELLOW


def _snap(records: dict[str, list[str]]) -> DnsSnapshot:
    return DnsSnapshot(fetched_at=datetime(2026, 5, 23, tzinfo=UTC), records=records)


def test_diff_returns_empty_when_no_previous() -> None:
    """Premier run — pas de baseline, donc pas de diff (sinon faux positifs)."""
    current = _snap({"omnividens.fr:A": ["1.2.3.4"]})
    assert diff_snapshots(None, current) == []


def test_diff_detects_added_record_value() -> None:
    previous = _snap({"omnividens.fr:A": ["1.2.3.4"]})
    current = _snap({"omnividens.fr:A": ["1.2.3.4", "5.6.7.8"]})
    changes = diff_snapshots(previous, current)
    assert len(changes) == 1
    assert changes[0].added == ["5.6.7.8"]
    assert changes[0].removed == []
    assert changes[0].is_critical is True


def test_diff_flags_critical_when_root_a_changes() -> None:
    previous = _snap({"omnividens.fr:A": ["1.2.3.4"]})
    current = _snap({"omnividens.fr:A": ["9.9.9.9"]})
    changes = diff_snapshots(previous, current)
    assert changes[0].is_critical is True


def test_diff_neutral_when_only_txt_changes() -> None:
    previous = _snap({"omnividens.fr:TXT": ["v=spf1 -all"]})
    current = _snap({"omnividens.fr:TXT": ["v=spf1 include:_spf.ovh.net -all"]})
    changes = diff_snapshots(previous, current)
    assert len(changes) == 1
    assert changes[0].is_critical is False


def test_classify_changes_distinguishes_neutral_vs_critical() -> None:
    previous = _snap(
        {"omnividens.fr:A": ["1.2.3.4"], "omnividens.fr:TXT": ["old-spf"]}
    )
    only_txt = diff_snapshots(
        previous,
        _snap({"omnividens.fr:A": ["1.2.3.4"], "omnividens.fr:TXT": ["new-spf"]}),
    )
    assert classify_changes(only_txt) == "neutral"

    with_a = diff_snapshots(
        previous,
        _snap({"omnividens.fr:A": ["9.9.9.9"], "omnividens.fr:TXT": ["new-spf"]}),
    )
    assert classify_changes(with_a) == "critical"
    assert classify_changes([]) == "none"


def test_build_report_green_when_no_change() -> None:
    report = build_report(_snap({"omnividens.fr:A": ["1.2.3.4"]}), changes=[])
    assert report.alert_color == GREEN
    assert report.should_alert is False
    assert "stable" in report.summary


def test_build_report_yellow_when_neutral() -> None:
    previous = _snap({"omnividens.fr:TXT": ["old"]})
    current = _snap({"omnividens.fr:TXT": ["new"]})
    changes = diff_snapshots(previous, current)
    report = build_report(current, changes)
    assert report.alert_color == YELLOW


def test_build_report_red_when_critical() -> None:
    previous = _snap({"omnividens.fr:A": ["1.2.3.4"]})
    current = _snap({"omnividens.fr:A": ["9.9.9.9"]})
    changes = diff_snapshots(previous, current)
    report = build_report(current, changes)
    assert report.alert_color == RED


def test_save_and_load_snapshot_roundtrip(tmp_path: Path) -> None:
    snap = _snap(
        {
            "omnividens.fr:A": ["1.2.3.4"],
            "omnividens.fr:MX": ["10 mx0.mail.ovh.net."],
        }
    )
    save_snapshot(snap, "omnividens.fr", base_dir=tmp_path)
    reloaded = load_previous("omnividens.fr", base_dir=tmp_path)
    assert reloaded is not None
    assert reloaded.records == snap.records


def test_load_previous_returns_none_when_missing(tmp_path: Path) -> None:
    assert load_previous("absent.example", base_dir=tmp_path) is None


def test_embed_includes_added_and_removed_lines() -> None:
    previous = _snap({"omnividens.fr:A": ["1.2.3.4"]})
    current = _snap({"omnividens.fr:A": ["9.9.9.9"]})
    changes = diff_snapshots(previous, current)
    embed = build_dns_embed(build_report(current, changes))
    field_text = embed.fields[0].value
    assert "+ 9.9.9.9" in field_text
    assert "- 1.2.3.4" in field_text
