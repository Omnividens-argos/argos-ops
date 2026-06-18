"""``BackupVerifierScript`` — un backup récent existe-t-il ? (archi v2, S8).

Scanne un dossier de backups (``data/backups/`` par défaut) et classe le plus
récent : vert ≤ 24 h, jaune ≤ 72 h, rouge au-delà ou si aucun backup. 100 %
filesystem, déterministe. ``backup_dir`` est injectable (tests hermétiques).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from argos_ops.config import REPO_ROOT
from argos_ops.poles.config import POLES_DIR
from argos_ops.poles.sre.base import BaseSreScript
from argos_ops.poles.sre.report import Severity, SreReport

BACKUP_GLOBS = ("*.sql", "*.sql.gz", "*.dump", "*.dump.gz", "*.tar.gz")
MAX_AGE_HOURS = 24.0
STALE_AGE_HOURS = 72.0
DEFAULT_BACKUP_DIR = REPO_ROOT / "data" / "backups"


@dataclass(frozen=True)
class BackupSnapshot:
    """Photo de l'état des backups."""

    most_recent: str | None
    age_hours: float | None
    file_count: int
    status: str  # ok | stale | missing


def scan_backups(backup_dir: Path, *, now: datetime | None = None) -> BackupSnapshot:
    """Trouve le backup le plus récent par mtime et calcule son âge."""
    moment = now or datetime.now(UTC)
    files: list[Path] = []
    if backup_dir.exists():
        for pattern in BACKUP_GLOBS:
            files.extend(backup_dir.glob(pattern))
    if not files:
        return BackupSnapshot(most_recent=None, age_hours=None, file_count=0, status="missing")
    newest = max(files, key=lambda p: p.stat().st_mtime)
    mtime = datetime.fromtimestamp(newest.stat().st_mtime, tz=UTC)
    age_hours = (moment - mtime).total_seconds() / 3600.0
    if age_hours <= MAX_AGE_HOURS:
        st = "ok"
    elif age_hours <= STALE_AGE_HOURS:
        st = "stale"
    else:
        st = "missing"
    return BackupSnapshot(
        most_recent=newest.name, age_hours=age_hours, file_count=len(files), status=st
    )


_STATUS_SEVERITY: dict[str, Severity] = {"ok": "green", "stale": "yellow", "missing": "red"}


def build_report(snap: BackupSnapshot) -> SreReport:
    severity = _STATUS_SEVERITY[snap.status]
    if snap.most_recent is None:
        return SreReport("red", "Aucun backup trouvé.", "Aucun fichier dans le dossier de backups.")
    # Résumé STABLE (état catégoriel, pas l'âge live) ⇒ écriture mémoire idempotente
    # tant que l'état observé ne change pas (cf. contrat SreReport.summary). L'âge
    # précis vit dans le cockpit (statut temps réel), jamais dans le corps hashé.
    summary = f"{snap.file_count} backup(s) · le plus récent {snap.most_recent} ({snap.status})"
    return SreReport(severity, summary)


class BackupVerifierScript(BaseSreScript):
    """Vérifie la fraîcheur du dernier backup."""

    name = "backup_verifier"

    def __init__(self, *, poles_root: Path = POLES_DIR, backup_dir: Path | None = None) -> None:
        super().__init__(poles_root=poles_root)
        self._backup_dir = backup_dir or DEFAULT_BACKUP_DIR

    async def check(self) -> SreReport:
        return build_report(scan_backups(self._backup_dir))


__all__ = [
    "BACKUP_GLOBS",
    "MAX_AGE_HOURS",
    "STALE_AGE_HOURS",
    "BackupSnapshot",
    "BackupVerifierScript",
    "build_report",
    "scan_backups",
]
