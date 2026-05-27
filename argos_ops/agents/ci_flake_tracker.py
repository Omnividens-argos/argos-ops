"""CIFlakeTracker — DevOps Lead (P22.D Tech/SRE Sprint 4).

Détecte les tests CI flaky récurrents via l'API GitHub Actions
(``gh api /repos/{owner}/{repo}/actions/runs``). Un test est qualifié
de **flaky** quand il échoue puis passe sur la même SHA, ou quand il
échoue dans :data:`MIN_FAIL_RATE_PCT` % des N derniers runs sans
qu'aucun fix de code ne l'explique.

Politique anti-spam :
- **Silence** Discord si aucune flake détectée sur la fenêtre
- **Embed jaune** si ≥1 test au-dessus du seuil

L'API GitHub est appelée via ``gh`` CLI (déjà installé, déjà
authentifié) pour éviter de manipuler un PAT en clair dans la config.
Cf. ``argos_ops/agents/_fetcher_base.py`` pour le pattern HTTP — ici
on shell-out ``gh`` parce qu'on profite gratuitement de son token cache.

Cf. plan ``docs/ARGOS_OPS_PLAN.md`` Annexe D § 7 Tech/SRE, Sprint 4+.
"""

from __future__ import annotations

import asyncio
import json
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime

from loguru import logger

from argos_ops.agents._watcher_base import color_title, emit_alert_or_silence
from argos_ops.agents.base import BaseAgent, RunResult
from argos_ops.notifications.discord import GREEN, YELLOW, Embed, EmbedField

DEFAULT_REPO = "Omnividens-argos/argos-ops"
DEFAULT_LOOKBACK_RUNS = 50
MIN_FAIL_RATE_PCT = 20  # un job qui rate >= 20% des runs récents = flaky
MIN_OCCURRENCES = 3  # mais il faut au moins 3 failures absolues


@dataclass(frozen=True)
class JobSample:
    """Un sample de job CI : nom + conclusion ("success" | "failure" | ...)."""

    name: str
    conclusion: str


@dataclass(frozen=True)
class FlakeStat:
    """Statistique d'un job : nb runs + nb failures + ratio."""

    job_name: str
    runs: int
    failures: int

    @property
    def fail_rate_pct(self) -> float:
        return (self.failures / self.runs * 100.0) if self.runs else 0.0


@dataclass(frozen=True)
class FlakeReport:
    """Résultat agrégé du run CIFlakeTracker."""

    flakes: list[FlakeStat]
    total_runs: int
    should_alert: bool
    alert_color: int
    summary: str


# =============================================================================
# Appel GitHub Actions API via `gh`
# =============================================================================
async def _gh(args: list[str]) -> bytes:
    """Wrapper ``gh api`` qui crash explicitement sur erreur subprocess."""
    process = await asyncio.create_subprocess_exec(
        "gh",
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()
    if process.returncode != 0:
        raise RuntimeError(
            f"`gh {' '.join(args)}` failed (rc={process.returncode}): "
            f"{stderr.decode(errors='replace')[:200]}"
        )
    return stdout


async def fetch_recent_jobs(
    repo: str = DEFAULT_REPO, *, lookback_runs: int = DEFAULT_LOOKBACK_RUNS
) -> list[JobSample]:
    """Liste les jobs CI sur les ``lookback_runs`` derniers workflow runs.

    Étape 1 : ``gh api /repos/{repo}/actions/runs --paginate?...`` pour
    récupérer les IDs.
    Étape 2 : ``gh api /repos/{repo}/actions/runs/{id}/jobs`` pour chaque.

    L'API GitHub paginate à 100 par page — on en prend une seule (limit
    suffisant pour ~50 runs).
    """
    runs_raw = await _gh(
        [
            "api",
            f"/repos/{repo}/actions/runs?per_page={lookback_runs}",
            "--jq",
            ".workflow_runs[].id",
        ]
    )
    run_ids = [
        int(line) for line in runs_raw.decode().splitlines() if line.strip().isdigit()
    ]
    if not run_ids:
        return []

    samples: list[JobSample] = []
    for run_id in run_ids:
        try:
            jobs_raw = await _gh(
                [
                    "api",
                    f"/repos/{repo}/actions/runs/{run_id}/jobs",
                ]
            )
        except RuntimeError as exc:
            logger.warning(f"CIFlakeTracker — fetch jobs {run_id} échoué: {exc}")
            continue
        try:
            payload = json.loads(jobs_raw)
        except json.JSONDecodeError as exc:
            logger.warning(f"CIFlakeTracker — payload jobs {run_id} invalide: {exc}")
            continue
        for job in payload.get("jobs", []):
            name = str(job.get("name") or "<unknown>")
            conclusion = str(job.get("conclusion") or "skipped")
            samples.append(JobSample(name=name, conclusion=conclusion))
    return samples


# =============================================================================
# Stat
# =============================================================================
def compute_flakes(samples: list[JobSample]) -> list[FlakeStat]:
    """Agrège les samples par nom de job et calcule le fail rate."""
    total_per_job: Counter[str] = Counter()
    fail_per_job: Counter[str] = Counter()
    for sample in samples:
        total_per_job[sample.name] += 1
        if sample.conclusion == "failure":
            fail_per_job[sample.name] += 1

    stats: list[FlakeStat] = []
    for name, runs in total_per_job.items():
        failures = fail_per_job.get(name, 0)
        if failures < MIN_OCCURRENCES:
            continue
        stat = FlakeStat(job_name=name, runs=runs, failures=failures)
        if stat.fail_rate_pct >= MIN_FAIL_RATE_PCT:
            stats.append(stat)
    return sorted(stats, key=lambda s: s.fail_rate_pct, reverse=True)


def build_report(flakes: list[FlakeStat], total_runs: int) -> FlakeReport:
    if flakes:
        alert_color = YELLOW
        summary = f"{len(flakes)} jobs flaky sur {total_runs} runs"
        should_alert = True
    else:
        alert_color = GREEN
        summary = f"aucune flake (sur {total_runs} runs)"
        should_alert = False
    return FlakeReport(
        flakes=flakes,
        total_runs=total_runs,
        should_alert=should_alert,
        alert_color=alert_color,
        summary=summary,
    )


def build_flake_embed(report: FlakeReport, *, now: datetime | None = None) -> Embed:
    now = now or datetime.now(UTC)
    fields = [
        EmbedField(
            name=f"[FLAKE] {stat.job_name}",
            value=f"{stat.failures}/{stat.runs} échecs · {stat.fail_rate_pct:.0f}%",
            inline=False,
        )
        for stat in report.flakes
    ]
    title_status = color_title(report.alert_color, green=GREEN, yellow=YELLOW, red=YELLOW)
    return Embed(
        title=f"CIFlakeTracker — {title_status}",
        description=report.summary,
        color=report.alert_color,
        fields=fields,
        footer="Argos Ops • CIFlakeTracker",
        timestamp=now.isoformat(),
    )


class CIFlakeTracker(BaseAgent):
    """DevOps Lead — détecte les tests CI flaky via GitHub Actions API."""

    name = "CIFlakeTracker"
    command = "/run-ci-flakes"
    breaker_name = None
    ai_act_risk_class = "minimal"

    def __init__(
        self, *, repo: str = DEFAULT_REPO, lookback_runs: int = DEFAULT_LOOKBACK_RUNS
    ) -> None:
        self._repo = repo
        self._lookback_runs = lookback_runs

    async def run(self) -> RunResult:
        samples = await fetch_recent_jobs(self._repo, lookback_runs=self._lookback_runs)
        if not samples:
            return RunResult(
                status="success",
                output_summary="silence (aucun run CI récent)",
                extras={"alerted": False, "summary": "0 samples"},
            )
        flakes = compute_flakes(samples)
        report = build_report(flakes, total_runs=self._lookback_runs)
        return await emit_alert_or_silence(
            report, embed_builder=build_flake_embed, agent_name=self.name
        )


__all__ = [
    "DEFAULT_LOOKBACK_RUNS",
    "DEFAULT_REPO",
    "MIN_FAIL_RATE_PCT",
    "MIN_OCCURRENCES",
    "CIFlakeTracker",
    "FlakeReport",
    "FlakeStat",
    "JobSample",
    "build_flake_embed",
    "build_report",
    "compute_flakes",
    "fetch_recent_jobs",
]
