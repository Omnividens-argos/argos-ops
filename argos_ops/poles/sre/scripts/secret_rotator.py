"""``SecretRotatorScript`` — alerte sur les secrets trop vieux (archi v2, S8).

Lit ``data/poles/sre/secrets/rotation_log.yaml`` (sous ``poles_root``) : un
journal de rotation **noms + dates uniquement, jamais de valeurs** (fichier en
exception ``.gitignore``). Classe chaque secret par âge : vert ≤ 90 j, jaune
> 90 j (à tourner), rouge > 180 j (en retard) ou date manquante / invalide.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path

import yaml
from loguru import logger

from argos_ops.poles.config import POLES_DIR
from argos_ops.poles.sre.base import BaseSreScript
from argos_ops.poles.sre.report import Severity, SreReport, worst

SECRETS_FILE = ("secrets", "rotation_log.yaml")
DUE_DAYS = 90
OVERDUE_DAYS = 180

_STATUS_SEVERITY: dict[str, Severity] = {
    "ok": "green",
    "due": "yellow",
    "overdue": "red",
    "invalid": "red",
}


def secrets_path(*, poles_root: Path = POLES_DIR) -> Path:
    return poles_root / "sre" / SECRETS_FILE[0] / SECRETS_FILE[1]


@dataclass(frozen=True)
class SecretStatus:
    """État de rotation d'un secret (jamais sa valeur)."""

    name: str
    last_rotated: date | None
    age_days: int | None
    status: str  # ok | due | overdue | invalid
    notes: str | None = None


def _parse_date(value: object) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        return None


def evaluate_secrets(entries: list[dict[str, object]], *, today: date) -> list[SecretStatus]:
    """Classe chaque secret par âge (pur)."""
    out: list[SecretStatus] = []
    for entry in entries:
        name = str(entry.get("name", "?"))
        rotated = _parse_date(entry.get("last_rotated"))
        notes = str(entry["notes"]) if entry.get("notes") else None
        if rotated is None:
            out.append(SecretStatus(name, None, None, "invalid", notes))
            continue
        age = (today - rotated).days
        if age > OVERDUE_DAYS:
            st = "overdue"
        elif age > DUE_DAYS:
            st = "due"
        else:
            st = "ok"
        out.append(SecretStatus(name, rotated, age, st, notes))
    return out


def load_entries(*, poles_root: Path = POLES_DIR) -> list[dict[str, object]]:
    path = secrets_path(poles_root=poles_root)
    if not path.exists():
        return []
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        logger.warning(f"secret_rotator — YAML invalide : {exc}")
        return []
    items = raw.get("secrets") if isinstance(raw, dict) else None
    return [i for i in items if isinstance(i, dict)] if isinstance(items, list) else []


def build_report(statuses: list[SecretStatus]) -> SreReport:
    if not statuses:
        return SreReport("green", "Aucun secret suivi (rotation_log.yaml vide ou absent).")
    counts = {k: sum(1 for s in statuses if s.status == k) for k in _STATUS_SEVERITY}
    severity = worst(*(_STATUS_SEVERITY[s.status] for s in statuses))
    summary = (
        f"{counts['ok']} ok · {counts['due']} à tourner · "
        f"{counts['overdue']} en retard · {counts['invalid']} invalide(s)"
    )
    flagged = [s for s in statuses if s.status != "ok"]
    detail = "\n".join(
        f"- {s.name} : {s.status}" + (f" ({s.age_days} j)" if s.age_days is not None else "")
        for s in sorted(flagged, key=lambda x: x.name)
    )
    return SreReport(severity, summary, detail)


class SecretRotatorScript(BaseSreScript):
    """Alerte sur les secrets dépassant le seuil de rotation."""

    name = "secret_rotator"

    async def check(self) -> SreReport:
        today = datetime.now(UTC).date()
        return build_report(evaluate_secrets(load_entries(poles_root=self.poles_root), today=today))


__all__ = [
    "DUE_DAYS",
    "OVERDUE_DAYS",
    "SecretRotatorScript",
    "SecretStatus",
    "build_report",
    "evaluate_secrets",
    "load_entries",
    "secrets_path",
]
