"""SecretRotator — Security Engineer de la flotte (P22.C Tech/SRE Sprint 4).

Lit ``data/secrets/rotation_log.yaml`` et alerte Discord si un secret
n'a pas été rotaté depuis plus de :data:`MAX_AGE_DAYS` (90 j par défaut).

**Le fichier ne contient JAMAIS les valeurs des secrets** — uniquement
leur nom (visible humain) et la date de dernière rotation. C'est un
journal de discipline, pas un vault.

Politique anti-spam :
- **Silence** Discord si tous les secrets sont rotés < 90 j
- **Embed jaune** si ≥1 secret entre 90 j et 180 j
- **Embed rouge** si ≥1 secret > 180 j ou date introuvable

Cf. plan ``docs/ARGOS_OPS_PLAN.md`` Annexe D § 7 Tech/SRE, Sprint 4.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Literal

import yaml

from argos_ops.agents._watcher_base import color_title, emit_alert_or_silence
from argos_ops.agents.base import BaseAgent, RunResult
from argos_ops.config import REPO_ROOT
from argos_ops.notifications.discord import GREEN, RED, YELLOW, Embed, EmbedField

SecretAgeStatus = Literal["ok", "due", "overdue", "invalid"]

DEFAULT_ROTATION_LOG_PATH: Path = REPO_ROOT / "data" / "secrets" / "rotation_log.yaml"
MAX_AGE_DAYS = 90
OVERDUE_DAYS = 180


@dataclass(frozen=True)
class SecretEntry:
    """Une ligne du journal de rotation."""

    name: str
    last_rotated: date | None
    notes: str | None
    age_days: int | None
    status: SecretAgeStatus


@dataclass(frozen=True)
class SecretRotationReport:
    """Résultat agrégé du run SecretRotator."""

    entries: list[SecretEntry]
    should_alert: bool
    alert_color: int
    summary: str


# =============================================================================
# Lecture + classification
# =============================================================================
def _parse_date(value: object) -> date | None:
    """Accepte ``date``, ``datetime``, ou ``"YYYY-MM-DD"``. None sinon."""
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        try:
            return date.fromisoformat(value)
        except ValueError:
            return None
    return None


def _classify(age_days: int | None) -> SecretAgeStatus:
    if age_days is None:
        return "invalid"
    if age_days > OVERDUE_DAYS:
        return "overdue"
    if age_days > MAX_AGE_DAYS:
        return "due"
    return "ok"


def load_entries(
    path: Path = DEFAULT_ROTATION_LOG_PATH, *, today: date | None = None
) -> list[SecretEntry]:
    """Lit le YAML et calcule l'âge + le statut de chaque secret."""
    today = today or datetime.now(UTC).date()
    if not path.exists():
        return []
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    rows = raw.get("secrets", []) or []
    entries: list[SecretEntry] = []
    for row in rows:
        name = row.get("name")
        if not name:
            continue
        last_rotated = _parse_date(row.get("last_rotated"))
        age_days = (today - last_rotated).days if last_rotated is not None else None
        entries.append(
            SecretEntry(
                name=name,
                last_rotated=last_rotated,
                notes=row.get("notes"),
                age_days=age_days,
                status=_classify(age_days),
            )
        )
    return entries


# =============================================================================
# Décision d'alerte
# =============================================================================
def build_report(entries: list[SecretEntry]) -> SecretRotationReport:
    """Construit le report — silence si tous ``ok``."""
    has_overdue_or_invalid = any(e.status in ("overdue", "invalid") for e in entries)
    has_due = any(e.status == "due" for e in entries)
    should_alert = has_overdue_or_invalid or has_due

    if has_overdue_or_invalid:
        alert_color = RED
    elif has_due:
        alert_color = YELLOW
    else:
        alert_color = GREEN

    ok = sum(1 for e in entries if e.status == "ok")
    due = sum(1 for e in entries if e.status == "due")
    overdue = sum(1 for e in entries if e.status == "overdue")
    invalid = sum(1 for e in entries if e.status == "invalid")
    summary = f"{ok} ok · {due} due · {overdue} overdue · {invalid} invalid"

    return SecretRotationReport(
        entries=entries,
        should_alert=should_alert,
        alert_color=alert_color,
        summary=summary,
    )


# =============================================================================
# Formatting
# =============================================================================
_STATUS_ICON: dict[SecretAgeStatus, str] = {
    "ok": "[OK]",
    "due": "[DUE]",
    "overdue": "[OVR]",
    "invalid": "[INV]",
}


def _format_entry_value(entry: SecretEntry) -> str:
    if entry.last_rotated is None:
        return f"<no rotation date> · notes: {entry.notes or 'n/a'}"
    parts = [
        f"rotated {entry.last_rotated.isoformat()}",
        f"age {entry.age_days}j",
    ]
    if entry.notes:
        parts.append(entry.notes[:160])
    return " · ".join(parts)


def build_secret_embed(
    report: SecretRotationReport, *, now: datetime | None = None
) -> Embed:
    """Construit l'embed Discord — un field par secret due/overdue/invalid."""
    now = now or datetime.now(UTC)
    fields = [
        EmbedField(
            name=f"{_STATUS_ICON[e.status]} {e.name}",
            value=_format_entry_value(e),
            inline=False,
        )
        for e in report.entries
        if e.status != "ok"
    ]
    title_status = color_title(report.alert_color, green=GREEN, yellow=YELLOW, red=RED)
    return Embed(
        title=f"SecretRotator — {title_status}",
        description=report.summary,
        color=report.alert_color,
        fields=fields,
        footer="Argos Ops • SecretRotator",
        timestamp=now.isoformat(),
    )


# =============================================================================
# Agent
# =============================================================================
class SecretRotator(BaseAgent):
    """Security Engineer — alerte sur secrets non rotés depuis > 90j."""

    name = "SecretRotator"
    command = "/run-secret-audit"
    breaker_name = None
    ai_act_risk_class = "minimal"

    def __init__(self, *, rotation_log_path: Path = DEFAULT_ROTATION_LOG_PATH) -> None:
        self._path = rotation_log_path

    async def run(self) -> RunResult:
        entries = load_entries(self._path)
        report = build_report(entries)
        return await emit_alert_or_silence(
            report, embed_builder=build_secret_embed, agent_name=self.name
        )


__all__ = [
    "DEFAULT_ROTATION_LOG_PATH",
    "MAX_AGE_DAYS",
    "OVERDUE_DAYS",
    "SecretAgeStatus",
    "SecretEntry",
    "SecretRotationReport",
    "SecretRotator",
    "build_report",
    "build_secret_embed",
    "load_entries",
]
