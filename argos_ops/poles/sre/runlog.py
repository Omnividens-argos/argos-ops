"""Journal **append-only** des runs de scripts SRE (archi v2, S8).

Le pôle SRE est purement déterministe et **local-first** (D-017) : il n'y a ni
DB ni table ``agent_runs``. La télémétrie opérationnelle (statut temps réel,
perf P50/P95, historique des runs) est dérivée d'un unique journal
``data/poles/sre/runlog.jsonl`` — **1 ligne JSON par run**.

Chaque ligne porte :

- ``status``   : le run s'est-il exécuté ? ``success`` / ``failed`` / ``skipped``.
- ``severity`` : couleur du **constat** du check (vert / jaune / rouge), distincte
  de ``status`` (un run ``success`` peut constater du ``red``).
- ``duration_ms`` : durée mesurée — alimente les percentiles P50/P95.

Append-only : on n'édite jamais une ligne (trace d'audit). Lecture best-effort :
une ligne illisible est loguée puis sautée, jamais fatale.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from loguru import logger

from argos_ops.poles.config import POLES_DIR
from argos_ops.poles.sre.report import Severity

SRE_POLE = "sre"
RUNLOG_FILE = "runlog.jsonl"

# Statut d'exécution du run (le check a-t-il tourné) — distinct de la sévérité.
RunStatus = str  # "success" | "failed" | "skipped"


def runlog_path(*, poles_root: Path = POLES_DIR) -> Path:
    return poles_root / SRE_POLE / RUNLOG_FILE


def _utcnow() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True)
class RunLogEntry:
    """Un run journalisé d'un script SRE."""

    at: datetime
    script: str
    status: str  # success | failed | skipped
    severity: Severity
    duration_ms: float
    summary: str
    error: str | None = None
    pole: str = SRE_POLE


def _entry_to_payload(entry: RunLogEntry) -> dict[str, object]:
    return {
        "at": entry.at.isoformat(),
        "pole": entry.pole,
        "script": entry.script,
        "status": entry.status,
        "severity": entry.severity,
        "duration_ms": round(entry.duration_ms, 3),
        "summary": entry.summary,
        "error": entry.error,
    }


def _parse_dt(value: object) -> datetime | None:
    if value is None:
        return None
    try:
        dt = value if isinstance(value, datetime) else datetime.fromisoformat(str(value))
    except ValueError:
        return None
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=UTC)


def _coerce_severity(value: object) -> Severity:
    if value == "yellow":
        return "yellow"
    if value == "red":
        return "red"
    return "green"


def _entry_from_payload(raw: object) -> RunLogEntry | None:
    if not isinstance(raw, dict):
        return None
    at = _parse_dt(raw.get("at"))
    if at is None:
        return None
    try:
        duration = float(raw.get("duration_ms") or 0.0)
    except (ValueError, TypeError):
        duration = 0.0
    return RunLogEntry(
        at=at,
        script=str(raw.get("script", "")),
        status=str(raw.get("status", "")),
        severity=_coerce_severity(raw.get("severity")),
        duration_ms=duration,
        summary=str(raw.get("summary", "")),
        error=(str(raw["error"]) if raw.get("error") is not None else None),
        pole=str(raw.get("pole", SRE_POLE)),
    )


def append_run(entry: RunLogEntry, *, poles_root: Path = POLES_DIR) -> RunLogEntry:
    """Journalise un run (append 1 ligne JSON). Crée le dossier au besoin."""
    path = runlog_path(poles_root=poles_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(_entry_to_payload(entry), ensure_ascii=False) + "\n")
    logger.debug(f"sre.runlog : {entry.script} → {entry.status}/{entry.severity}")
    return entry


def load_runs(
    *, script: str | None = None, limit: int | None = None, poles_root: Path = POLES_DIR
) -> list[RunLogEntry]:
    """Relit le journal, du plus récent au plus ancien (filtre optionnel par script)."""
    path = runlog_path(poles_root=poles_root)
    if not path.exists():
        return []
    entries: list[RunLogEntry] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            raw = json.loads(line)
        except json.JSONDecodeError as exc:
            logger.warning(f"sre.runlog : ligne illisible sautée — {exc}")
            continue
        entry = _entry_from_payload(raw)
        if entry is None or (script is not None and entry.script != script):
            continue
        entries.append(entry)
    # Tri total déterministe : (at, script) décroissant — l'ordre du fichier ne
    # doit pas fuiter quand deux runs partagent le même horodatage.
    entries.sort(key=lambda e: (e.at, e.script), reverse=True)
    return entries[:limit] if limit is not None else entries


def latest_per_script(*, poles_root: Path = POLES_DIR) -> dict[str, RunLogEntry]:
    """Dernier run de chaque script (le plus récent gagne)."""
    out: dict[str, RunLogEntry] = {}
    for entry in load_runs(poles_root=poles_root):  # déjà trié récent → vieux
        if entry.script not in out:
            out[entry.script] = entry
    return out


def percentiles(durations: list[float]) -> tuple[float | None, float | None]:
    """P50 / P95 (méthode du rang le plus proche). ``(None, None)`` si vide."""
    if not durations:
        return None, None
    ordered = sorted(durations)
    n = len(ordered)

    def _pick(p: float) -> float:
        rank = max(1, math.ceil(p * n))
        return ordered[rank - 1]

    return _pick(0.50), _pick(0.95)


def script_percentiles(
    script: str, *, window: int = 50, poles_root: Path = POLES_DIR
) -> tuple[float | None, float | None, int]:
    """Percentiles de durée d'un script sur ses ``window`` derniers runs exécutés.

    Ne compte que les runs réellement exécutés (``skipped`` exclu — durée nulle
    non représentative). Renvoie ``(p50, p95, n_échantillons)``.
    """
    runs = [
        r
        for r in load_runs(script=script, limit=window, poles_root=poles_root)
        if r.status != "skipped"
    ]
    p50, p95 = percentiles([r.duration_ms for r in runs])
    return p50, p95, len(runs)


def runs_today(script: str, *, now: datetime | None = None, poles_root: Path = POLES_DIR) -> int:
    """Nombre de runs **exécutés** d'un script depuis minuit UTC (pour daily_limit)."""
    moment = now or _utcnow()
    midnight = moment.astimezone(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    return sum(
        1
        for r in load_runs(script=script, poles_root=poles_root)
        if r.status != "skipped" and r.at >= midnight
    )


__all__ = [
    "RUNLOG_FILE",
    "SRE_POLE",
    "RunLogEntry",
    "RunStatus",
    "append_run",
    "latest_per_script",
    "load_runs",
    "percentiles",
    "runlog_path",
    "runs_today",
    "script_percentiles",
]
