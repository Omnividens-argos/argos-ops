"""Tests unitaires de :mod:`argos_ops.agents.backup_verifier` (P22.C).

Couvre :
- ``inspect_backups`` : dossier absent / vide / multi-fichiers
- ``inspect_backups`` : classification ok / stale / missing selon âge
- ``build_report`` : couleur RED/YELLOW/GREEN
"""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

from argos_ops.agents.backup_verifier import (
    BackupSnapshot,
    build_report,
    inspect_backups,
)
from argos_ops.notifications.discord import GREEN, RED, YELLOW


def _touch_with_age(path: Path, *, hours_ago: float) -> None:
    """Crée un fichier vide et force son mtime à ``now - hours_ago``."""
    path.write_bytes(b"")
    target = (datetime.now(UTC) - timedelta(hours=hours_ago)).timestamp()
    os.utime(path, (target, target))


# =============================================================================
# inspect_backups
# =============================================================================
def test_inspect_backups_missing_directory_returns_missing(tmp_path: Path) -> None:
    snapshot = inspect_backups(tmp_path / "nope")
    assert snapshot.status == "missing"
    assert snapshot.file_count == 0
    assert snapshot.most_recent_file is None


def test_inspect_backups_empty_directory_returns_missing(tmp_path: Path) -> None:
    snapshot = inspect_backups(tmp_path)
    assert snapshot.status == "missing"
    assert snapshot.file_count == 0


def test_inspect_backups_finds_most_recent_across_files(tmp_path: Path) -> None:
    """Trois fichiers d'âges différents → renvoie le plus récent."""
    _touch_with_age(tmp_path / "old.sql", hours_ago=100.0)
    _touch_with_age(tmp_path / "mid.sql.gz", hours_ago=50.0)
    _touch_with_age(tmp_path / "fresh.dump", hours_ago=2.0)
    snapshot = inspect_backups(tmp_path)
    assert snapshot.file_count == 3
    assert snapshot.most_recent_file is not None
    assert snapshot.most_recent_file.name == "fresh.dump"


def test_inspect_backups_classifies_ok_when_under_24h(tmp_path: Path) -> None:
    _touch_with_age(tmp_path / "recent.sql", hours_ago=5.0)
    snapshot = inspect_backups(tmp_path)
    assert snapshot.status == "ok"


def test_inspect_backups_classifies_stale_between_24h_and_72h(tmp_path: Path) -> None:
    _touch_with_age(tmp_path / "old.sql", hours_ago=48.0)
    snapshot = inspect_backups(tmp_path)
    assert snapshot.status == "stale"


def test_inspect_backups_classifies_missing_above_72h(tmp_path: Path) -> None:
    _touch_with_age(tmp_path / "ancient.sql", hours_ago=200.0)
    snapshot = inspect_backups(tmp_path)
    assert snapshot.status == "missing"


# =============================================================================
# build_report
# =============================================================================
def _snap(status: str, *, age: float | None = 5.0) -> BackupSnapshot:
    return BackupSnapshot(
        most_recent_file=Path("/tmp/test.sql") if age is not None else None,
        most_recent_age_hours=age,
        file_count=1 if age is not None else 0,
        status=status,  # type: ignore[arg-type]
    )


def test_build_report_green_when_ok() -> None:
    report = build_report(_snap("ok"))
    assert report.alert_color == GREEN
    assert report.should_alert is False


def test_build_report_yellow_when_stale() -> None:
    report = build_report(_snap("stale", age=48.0))
    assert report.alert_color == YELLOW
    assert report.should_alert is True


def test_build_report_red_when_missing() -> None:
    report = build_report(_snap("missing", age=None))
    assert report.alert_color == RED
    assert report.should_alert is True
    assert "aucun backup" in report.summary
