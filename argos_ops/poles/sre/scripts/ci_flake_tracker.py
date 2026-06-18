"""``CiFlakeTrackerScript`` — détection de tests CI flaky (archi v2, S8).

Interroge l'historique GitHub Actions (via la CLI ``gh``) sur les ``lookback``
derniers runs et repère les jobs **flaky** : ≥ 20 % d'échecs ET ≥ 3 échecs. Tout
flake ⇒ jaune (jamais rouge : c'est un signal de fragilité, pas une panne). Le
fetcher de jobs est injectable (tests hermétiques). ``gh`` indisponible ⇒ jaune
(« historique CI illisible »).
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path

from loguru import logger

from argos_ops.poles.config import POLES_DIR
from argos_ops.poles.sre.base import BaseSreScript
from argos_ops.poles.sre.report import SreReport

DEFAULT_REPO = "Omnividens-argos/argos-ops"
DEFAULT_LOOKBACK = 50
MIN_FAIL_RATE_PCT = 20.0
MIN_OCCURRENCES = 3


@dataclass(frozen=True)
class JobRun:
    """Une exécution de job CI (un job d'un run)."""

    name: str
    conclusion: str  # success | failure | cancelled | skipped | ...


@dataclass(frozen=True)
class FlakeStat:
    """Statistiques de fragilité d'un job."""

    job_name: str
    runs: int
    failures: int
    fail_rate_pct: float


# fetcher : (repo, lookback) → (n_runs analysés, jobs aplatis sur ces runs).
JobsFetcher = Callable[[str, int], Awaitable[tuple[int, list[JobRun]]]]


def detect_flakes(jobs: list[JobRun]) -> list[FlakeStat]:
    """Agrège par nom de job et repère les flaky (pur). Tri par taux décroissant."""
    runs: dict[str, int] = {}
    failures: dict[str, int] = {}
    for job in jobs:
        runs[job.name] = runs.get(job.name, 0) + 1
        if job.conclusion == "failure":
            failures[job.name] = failures.get(job.name, 0) + 1
    flakes: list[FlakeStat] = []
    for name, total in runs.items():
        fails = failures.get(name, 0)
        rate = (fails / total) * 100.0 if total else 0.0
        if fails >= MIN_OCCURRENCES and rate >= MIN_FAIL_RATE_PCT:
            flakes.append(FlakeStat(name, total, fails, rate))
    flakes.sort(key=lambda f: (-f.fail_rate_pct, f.job_name))
    return flakes


async def real_jobs_fetcher(repo: str, lookback: int) -> tuple[int, list[JobRun]]:
    """Récupère les jobs des ``lookback`` derniers runs via ``gh api``."""

    async def _gh(path: str) -> dict[str, object]:
        proc = await asyncio.create_subprocess_exec(
            "gh",
            "api",
            path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise RuntimeError(f"gh api {path} : {stderr.decode('utf-8', 'replace')[:160]}")
        parsed = json.loads(stdout.decode("utf-8", "replace"))
        return parsed if isinstance(parsed, dict) else {}

    runs_body = await _gh(f"/repos/{repo}/actions/runs?per_page={lookback}")
    workflow_runs = runs_body.get("workflow_runs", [])
    run_rows = workflow_runs if isinstance(workflow_runs, list) else []
    run_ids = [r.get("id") for r in run_rows if isinstance(r, dict)]
    jobs: list[JobRun] = []
    for run_id in run_ids:
        jobs_body = await _gh(f"/repos/{repo}/actions/runs/{run_id}/jobs")
        job_rows = jobs_body.get("jobs", [])
        for job in job_rows if isinstance(job_rows, list) else []:
            if isinstance(job, dict):
                jobs.append(JobRun(str(job.get("name", "?")), str(job.get("conclusion") or "")))
    return len(run_ids), jobs


def build_report(n_runs: int, flakes: list[FlakeStat]) -> SreReport:
    if not flakes:
        return SreReport("green", f"Aucun job flaky sur {n_runs} run(s).")
    summary = f"{len(flakes)} job(s) flaky sur {n_runs} run(s)"
    detail = "\n".join(
        f"- {f.job_name} : {f.failures}/{f.runs} échecs ({f.fail_rate_pct:.0f}%)" for f in flakes
    )
    return SreReport("yellow", summary, detail)


class CiFlakeTrackerScript(BaseSreScript):
    """Repère les jobs CI flaky sur l'historique GitHub Actions."""

    name = "ci_flake_tracker"

    def __init__(
        self,
        *,
        poles_root: Path = POLES_DIR,
        repo: str = DEFAULT_REPO,
        lookback: int = DEFAULT_LOOKBACK,
        fetcher: JobsFetcher | None = None,
    ) -> None:
        super().__init__(poles_root=poles_root)
        self._repo = repo
        self._lookback = lookback
        self._fetcher = fetcher or real_jobs_fetcher

    async def check(self) -> SreReport:
        try:
            n_runs, jobs = await self._fetcher(self._repo, self._lookback)
        except (OSError, RuntimeError, json.JSONDecodeError) as exc:
            logger.warning(f"ci_flake_tracker — historique CI illisible : {exc}")
            return SreReport("yellow", f"Historique CI illisible : {type(exc).__name__}")
        return build_report(n_runs, detect_flakes(jobs))


__all__ = [
    "DEFAULT_LOOKBACK",
    "DEFAULT_REPO",
    "MIN_FAIL_RATE_PCT",
    "MIN_OCCURRENCES",
    "CiFlakeTrackerScript",
    "FlakeStat",
    "JobRun",
    "JobsFetcher",
    "build_report",
    "detect_flakes",
    "real_jobs_fetcher",
]
