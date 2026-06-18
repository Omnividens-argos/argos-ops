"""Journal **append-only** des runs lancés par l'orchestrateur de flotte (archi v2, S9).

L'orchestrateur de flotte (:mod:`argos_ops.poles.fleet`) lance des scripts de
**tous** les pôles. Pour savoir, au plan suivant, quand un script a tourné pour la
dernière fois (cadence cron + ``daily_limit``), il lui faut un journal — mais on
**ne touche pas** au runlog SRE (``data/poles/sre/runlog.jsonl``), réservé au
cockpit SRE et indexé par nom de script seul. La flotte a donc son propre journal
``data/poles/fleet_runlog.jsonl``, indexé par couple ``(pole, script)`` pour ne
jamais confondre deux pôles.

1 ligne JSON par run. Append-only (trace d'audit) ; lecture best-effort (une ligne
illisible est loguée puis sautée, jamais fatale). 100 % fichiers (D-017).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from loguru import logger

from argos_ops.poles.config import POLES_DIR

FLEET_RUNLOG_FILE = "fleet_runlog.jsonl"


def fleet_runlog_path(*, poles_root: Path = POLES_DIR) -> Path:
    return poles_root / FLEET_RUNLOG_FILE


def _utcnow() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True)
class FleetRun:
    """Un run de script journalisé par l'orchestrateur de flotte."""

    at: datetime
    pole: str
    script: str
    status: str  # success | failed | skipped
    duration_ms: float
    summary: str = ""
    error: str | None = None


def _to_payload(run: FleetRun) -> dict[str, object]:
    return {
        "at": run.at.isoformat(),
        "pole": run.pole,
        "script": run.script,
        "status": run.status,
        "duration_ms": round(run.duration_ms, 3),
        "summary": run.summary,
        "error": run.error,
    }


def _parse_dt(value: object) -> datetime | None:
    if value is None:
        return None
    try:
        dt = value if isinstance(value, datetime) else datetime.fromisoformat(str(value))
    except ValueError:
        return None
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=UTC)


def _from_payload(raw: object) -> FleetRun | None:
    if not isinstance(raw, dict):
        return None
    at = _parse_dt(raw.get("at"))
    if at is None:
        return None
    try:
        duration = float(raw.get("duration_ms") or 0.0)
    except (ValueError, TypeError):
        duration = 0.0
    return FleetRun(
        at=at,
        pole=str(raw.get("pole", "")),
        script=str(raw.get("script", "")),
        status=str(raw.get("status", "")),
        duration_ms=duration,
        summary=str(raw.get("summary", "")),
        error=(str(raw["error"]) if raw.get("error") is not None else None),
    )


def append_fleet_run(run: FleetRun, *, poles_root: Path = POLES_DIR) -> FleetRun:
    """Journalise un run de flotte (append 1 ligne JSON). Crée le dossier au besoin."""
    path = fleet_runlog_path(poles_root=poles_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(_to_payload(run), ensure_ascii=False) + "\n")
    logger.debug(f"fleet_runlog : {run.pole}/{run.script} → {run.status}")
    return run


def load_fleet_runs(
    *,
    pole: str | None = None,
    script: str | None = None,
    limit: int | None = None,
    poles_root: Path = POLES_DIR,
) -> list[FleetRun]:
    """Relit le journal, du plus récent au plus ancien (filtres optionnels)."""
    path = fleet_runlog_path(poles_root=poles_root)
    if not path.exists():
        return []
    runs: list[FleetRun] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            raw = json.loads(line)
        except json.JSONDecodeError as exc:
            logger.warning(f"fleet_runlog : ligne illisible sautée — {exc}")
            continue
        run = _from_payload(raw)
        if run is None:
            continue
        if pole is not None and run.pole != pole:
            continue
        if script is not None and run.script != script:
            continue
        runs.append(run)
    # Tri total déterministe : (at, pole, script) décroissant.
    runs.sort(key=lambda r: (r.at, r.pole, r.script), reverse=True)
    return runs[:limit] if limit is not None else runs


def latest_per_pole_script(
    *, runs: list[FleetRun] | None = None, poles_root: Path = POLES_DIR
) -> dict[tuple[str, str], FleetRun]:
    """Dernier run de chaque couple ``(pole, script)`` (le plus récent gagne).

    ``runs`` (déjà trié récent → vieux, p.ex. le retour de :func:`load_fleet_runs`)
    évite de relire le journal — utile quand l'appelant l'a déjà chargé.
    """
    source = runs if runs is not None else load_fleet_runs(poles_root=poles_root)
    out: dict[tuple[str, str], FleetRun] = {}
    for run in source:  # trié récent → vieux ⇒ le premier vu est le plus récent
        key = (run.pole, run.script)
        if key not in out:
            out[key] = run
    return out


def runs_today_for(
    pole: str,
    script: str,
    *,
    now: datetime | None = None,
    runs: list[FleetRun] | None = None,
    poles_root: Path = POLES_DIR,
) -> int:
    """Runs **exécutés** d'un couple ``(pole, script)`` depuis minuit UTC (pour daily_limit).

    ``now`` naïf est interprété en UTC (convention de :mod:`argos_ops.poles.sre.schedule`),
    jamais en heure locale. ``runs`` pré-chargé évite de relire le journal.
    """
    moment = now or _utcnow()
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    midnight = moment.astimezone(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    source = (
        runs
        if runs is not None
        else load_fleet_runs(pole=pole, script=script, poles_root=poles_root)
    )
    return sum(
        1
        for r in source
        if r.pole == pole and r.script == script and r.status != "skipped" and r.at >= midnight
    )


__all__ = [
    "FLEET_RUNLOG_FILE",
    "FleetRun",
    "append_fleet_run",
    "fleet_runlog_path",
    "latest_per_pole_script",
    "load_fleet_runs",
    "runs_today_for",
]
