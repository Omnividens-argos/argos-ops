"""BackupVerifier — DevOps de la flotte (P22.C Tech/SRE Sprint 4).

Vérifie qu'un backup Postgres récent (< :data:`MAX_AGE_HOURS`) existe
dans ``data/backups/``. Alerte Discord si aucun backup récent.

Conventions de nommage acceptées (glob patterns) :
- ``*.sql``
- ``*.sql.gz``
- ``*.dump``
- ``*.dump.gz``

Politique anti-spam :
- **Silence** Discord si ≥1 backup dans la fenêtre fraîche (< 24h)
- **Embed jaune** si le backup le plus récent date de 24-72h
- **Embed rouge** si > 72h ou aucun backup trouvé

Cet agent **n'a pas de slash command** — il tourne via Task Scheduler
quotidien (``argos-ops-backup-verifier``).

Cf. plan ``docs/ARGOS_OPS_PLAN.md`` Annexe D § 7 Tech/SRE, Sprint 4.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from argos_ops.agents._watcher_base import color_title, emit_alert_or_silence, format_age
from argos_ops.agents.base import BaseAgent, IOItem, RunResult
from argos_ops.config import REPO_ROOT
from argos_ops.notifications.discord import GREEN, RED, YELLOW, Embed, EmbedField

BackupStatus = Literal["ok", "stale", "missing"]

DEFAULT_BACKUPS_DIR: Path = REPO_ROOT / "data" / "backups"
MAX_AGE_HOURS = 24.0
STALE_THRESHOLD_HOURS = 72.0
BACKUP_GLOBS: tuple[str, ...] = ("*.sql", "*.sql.gz", "*.dump", "*.dump.gz")


@dataclass(frozen=True)
class BackupSnapshot:
    """État du backup le plus récent trouvé."""

    most_recent_file: Path | None
    most_recent_age_hours: float | None
    file_count: int
    status: BackupStatus


@dataclass(frozen=True)
class BackupReport:
    """Résultat agrégé du run BackupVerifier."""

    snapshot: BackupSnapshot
    should_alert: bool
    alert_color: int
    summary: str


# =============================================================================
# Inspection filesystem
# =============================================================================
def _list_backups(backups_dir: Path) -> list[Path]:
    if not backups_dir.exists():
        return []
    files: list[Path] = []
    for pattern in BACKUP_GLOBS:
        files.extend(p for p in backups_dir.glob(pattern) if p.is_file())
    return files


def inspect_backups(
    backups_dir: Path = DEFAULT_BACKUPS_DIR, *, now: datetime | None = None
) -> BackupSnapshot:
    """Trouve le backup le plus récent et calcule son âge en heures."""
    now = now or datetime.now(UTC)
    files = _list_backups(backups_dir)
    if not files:
        return BackupSnapshot(
            most_recent_file=None,
            most_recent_age_hours=None,
            file_count=0,
            status="missing",
        )

    most_recent = max(files, key=lambda p: p.stat().st_mtime)
    mtime = datetime.fromtimestamp(most_recent.stat().st_mtime, tz=UTC)
    age_hours = (now - mtime).total_seconds() / 3600.0

    status: BackupStatus
    if age_hours <= MAX_AGE_HOURS:
        status = "ok"
    elif age_hours <= STALE_THRESHOLD_HOURS:
        status = "stale"
    else:
        status = "missing"  # plus de 72h = on considère absent en pratique

    return BackupSnapshot(
        most_recent_file=most_recent,
        most_recent_age_hours=round(age_hours, 2),
        file_count=len(files),
        status=status,
    )


# =============================================================================
# Décision d'alerte
# =============================================================================
def build_report(snapshot: BackupSnapshot) -> BackupReport:
    """``ok`` → silence, ``stale`` → jaune, ``missing`` → rouge."""
    should_alert = snapshot.status != "ok"
    if snapshot.status == "missing":
        alert_color = RED
    elif snapshot.status == "stale":
        alert_color = YELLOW
    else:
        alert_color = GREEN

    if snapshot.most_recent_file is None:
        summary = "aucun backup trouvé"
    else:
        summary = (
            f"{snapshot.file_count} backup(s) · le plus récent: "
            f"{format_age(snapshot.most_recent_age_hours)}"
        )

    return BackupReport(
        snapshot=snapshot,
        should_alert=should_alert,
        alert_color=alert_color,
        summary=summary,
    )


# =============================================================================
# Formatting
# =============================================================================
_STATUS_ICON: dict[BackupStatus, str] = {
    "ok": "[OK]",
    "stale": "[STALE]",
    "missing": "[MISS]",
}


def build_backup_embed(report: BackupReport, *, now: datetime | None = None) -> Embed:
    """Construit l'embed Discord — un seul field récapitulatif."""
    now = now or datetime.now(UTC)
    snap = report.snapshot
    if snap.most_recent_file is None:
        value = (
            f"Aucun fichier matching {', '.join(BACKUP_GLOBS)} dans"
            f" `{DEFAULT_BACKUPS_DIR}`"
        )
    else:
        value = (
            f"file: `{snap.most_recent_file.name}`\n"
            f"age: {format_age(snap.most_recent_age_hours)}"
            f" (seuil {MAX_AGE_HOURS}h)\n"
            f"total backups: {snap.file_count}"
        )

    fields = [
        EmbedField(
            name=f"{_STATUS_ICON[snap.status]} Postgres backup",
            value=value,
            inline=False,
        )
    ]
    title_status = color_title(report.alert_color, green=GREEN, yellow=YELLOW, red=RED)
    return Embed(
        title=f"BackupVerifier — {title_status}",
        description=report.summary,
        color=report.alert_color,
        fields=fields,
        footer="Argos Ops • BackupVerifier",
        timestamp=now.isoformat(),
    )


# =============================================================================
# Agent
# =============================================================================
class BackupVerifier(BaseAgent):
    """DevOps — vérifie qu'un backup Postgres récent existe."""

    name = "BackupVerifier"
    command = None  # pas de slash command (cron quotidien)
    breaker_name = None
    ai_act_risk_class = "minimal"

    def __init__(self, *, backups_dir: Path = DEFAULT_BACKUPS_DIR) -> None:
        self._backups_dir = backups_dir

    async def run(self) -> RunResult:
        snapshot = inspect_backups(self._backups_dir)
        report = build_report(snapshot)
        inputs = [
            IOItem(
                label="Dossier de backups Postgres",
                kind="file",
                detail=", ".join(BACKUP_GLOBS),
                ref=str(self._backups_dir),
                count=snapshot.file_count,
            )
        ]
        outputs = [
            IOItem(
                label="Backup le plus récent",
                kind="file",
                detail=(
                    f"{snapshot.most_recent_file.name} "
                    f"({format_age(snapshot.most_recent_age_hours)}, {snapshot.status})"
                    if snapshot.most_recent_file is not None
                    else "aucun backup trouvé"
                ),
                ref=str(snapshot.most_recent_file)
                if snapshot.most_recent_file is not None
                else None,
            )
        ]
        return await emit_alert_or_silence(
            report,
            embed_builder=build_backup_embed,
            agent_name=self.name,
            inputs=inputs,
            outputs=outputs,
        )


__all__ = [
    "BACKUP_GLOBS",
    "DEFAULT_BACKUPS_DIR",
    "MAX_AGE_HOURS",
    "STALE_THRESHOLD_HOURS",
    "BackupReport",
    "BackupSnapshot",
    "BackupStatus",
    "BackupVerifier",
    "build_backup_embed",
    "build_report",
    "inspect_backups",
]
