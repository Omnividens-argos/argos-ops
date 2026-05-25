"""BoardReporter — Investor Relations (P22.E Direction Sprint 9).

Génère un board pack mensuel pandoc-ready dans
``data/strategy/board-YYYY-MM.md``. Contenu :

- MRR / ARR fin de mois
- Burn rate / runway estimés (depuis ``data/strategy/burn.yaml`` si présent)
- NRR (placeholder tant qu'on n'a pas d'expansion / churn historisés)
- Volume agent runs / breakers tripped / incidents (cross-link
  ``data/compliance/incidents/``)

Skill réutilisé : ``stripe-ops`` (P7) — calcul MRR/ARR à la même date que
``FinanceBot`` quotidien. En mode test, on accepte un override ``mrr_eur``
direct pour éviter l'appel Stripe.

Cf. plan ``docs/ARGOS_OPS_PLAN.md`` Annexe D § 1 Direction, Sprint 9.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from loguru import logger

from argos_ops.agents.base import BaseAgent, RunResult
from argos_ops.config import REPO_ROOT
from argos_ops.crm.db import session_scope
from argos_ops.crm.models import AgentRun
from argos_ops.crm.repository import sum_active_mrr_eur
from argos_ops.exceptions import AgentDataSourceError, AgentOutputError

DEFAULT_OUTPUT_DIR: Path = REPO_ROOT / "data" / "strategy"
DEFAULT_BURN_PATH: Path = REPO_ROOT / "data" / "strategy" / "burn.yaml"
DEFAULT_INCIDENTS_DIR: Path = REPO_ROOT / "data" / "compliance" / "incidents"


@dataclass(frozen=True)
class BoardMetrics:
    """Snapshot mensuel des KPIs board pack."""

    period: str  # YYYY-MM
    mrr_eur: Decimal
    arr_eur: Decimal
    burn_eur: Decimal | None
    runway_months: float | None
    nrr_pct: float | None
    runs_month: int
    breakers_tripped: int
    incidents_month: int


# =============================================================================
# Lecture des sources
# =============================================================================
def load_burn(path: Path) -> tuple[Decimal | None, float | None]:
    """Lit ``burn_eur`` + ``runway_months`` depuis le YAML.

    Retourne ``(None, None)`` si le fichier est absent — c'est OK pour
    un early stage où le founder n'a pas encore tracké son cash flow.
    """
    if not path.exists():
        return None, None
    try:
        import yaml

        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        burn = raw.get("burn_eur")
        runway = raw.get("runway_months")
        return (
            Decimal(str(burn)) if burn is not None else None,
            float(runway) if runway is not None else None,
        )
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        logger.warning(f"BoardReporter — burn.yaml illisible: {exc}")
        return None, None


def count_incidents_in_month(incidents_dir: Path, year: int, month: int) -> int:
    """Compte les post-mortems dans le mois (par préfixe filename ``YYYY-MM``)."""
    if not incidents_dir.exists():
        return 0
    prefix = f"{year:04d}-{month:02d}"
    return sum(1 for p in incidents_dir.glob("*.md") if p.stem.startswith(prefix))


# =============================================================================
# Rendu markdown
# =============================================================================
def render_board_pack(metrics: BoardMetrics) -> str:
    """Rend le markdown pandoc-ready."""
    lines = [
        "---",
        f"title: \"Argos Ops — Board Pack {metrics.period}\"",
        "author: \"Omnividens\"",
        f"date: \"{metrics.period}-01\"",
        "---",
        "",
        f"# Board Pack — {metrics.period}",
        "",
        "## Finance",
        "",
        f"- **MRR fin de mois** : {metrics.mrr_eur:.2f} €",
        f"- **ARR (12x MRR)** : {metrics.arr_eur:.2f} €",
    ]
    if metrics.burn_eur is not None:
        lines.append(f"- **Burn mensuel** : {metrics.burn_eur:.2f} €")
    else:
        lines.append("- **Burn mensuel** : _non tracké_")
    if metrics.runway_months is not None:
        lines.append(f"- **Runway estimé** : {metrics.runway_months:.1f} mois")
    else:
        lines.append("- **Runway estimé** : _non tracké_")
    if metrics.nrr_pct is not None:
        lines.append(f"- **NRR** : {metrics.nrr_pct:.1f}%")
    else:
        lines.append(
            "- **NRR** : _placeholder — pas assez de cohortes pour calcul fiable_"
        )

    lines.extend(
        [
            "",
            "## Opérations",
            "",
            f"- **Agent runs ce mois** : {metrics.runs_month}",
            f"- **Circuit breakers tripped** : {metrics.breakers_tripped}",
            f"- **Incidents internes loggés** : {metrics.incidents_month}",
            "",
            "## Décisions structurantes",
            "",
            "Voir [`docs/DECISIONS.md`](../../docs/DECISIONS.md) — décisions taggées P22.E ou postérieures.",
            "",
            "## TODO board",
            "",
            "- [ ] Valider le pricing (ICP Persona 1 vs Persona 3)",
            "- [ ] Décision hire / no hire AE",
            "- [ ] Revue compliance trimestrielle (RGPD + AI Act)",
            "",
            "---",
            "",
            "*Pandoc-ready : `pandoc board-YYYY-MM.md -o board-YYYY-MM.pdf --pdf-engine=xelatex`*",
            "",
        ]
    )
    return "\n".join(lines)


# =============================================================================
# Agent
# =============================================================================
class BoardReporter(BaseAgent):
    """Investor Relations — board pack mensuel."""

    name = "BoardReporter"
    command = "/run-board-pack"
    breaker_name = None
    ai_act_risk_class = "limited"

    def __init__(
        self,
        *,
        output_dir: Path = DEFAULT_OUTPUT_DIR,
        burn_path: Path = DEFAULT_BURN_PATH,
        incidents_dir: Path = DEFAULT_INCIDENTS_DIR,
        now: datetime | None = None,
        mrr_eur_override: Decimal | None = None,
        runs_count_override: int | None = None,
        breakers_count_override: int | None = None,
    ) -> None:
        self._output_dir = output_dir
        self._burn_path = burn_path
        self._incidents_dir = incidents_dir
        self._now = now or datetime.now(UTC)
        self._mrr_override = mrr_eur_override
        self._runs_override = runs_count_override
        self._breakers_override = breakers_count_override

    async def _fetch_mrr(self) -> Decimal:
        if self._mrr_override is not None:
            return self._mrr_override
        async with session_scope() as session:
            return await sum_active_mrr_eur(session)

    async def _fetch_runs_count(self, year: int, month: int) -> int:
        if self._runs_override is not None:
            return self._runs_override
        from sqlmodel import col, select

        start = datetime(year, month, 1, tzinfo=UTC)
        end = (start + timedelta(days=32)).replace(day=1)
        async with session_scope() as session:
            stmt = select(AgentRun).where(
                col(AgentRun.started_at) >= start,
                col(AgentRun.started_at) < end,
            )
            runs = list((await session.execute(stmt)).scalars().all())
            return len(runs)

    async def _fetch_breakers_tripped(self) -> int:
        if self._breakers_override is not None:
            return self._breakers_override
        from sqlmodel import col, select

        from argos_ops.crm.models import Breaker

        async with session_scope() as session:
            stmt = select(Breaker).where(col(Breaker.tripped).is_(True))
            return len(list((await session.execute(stmt)).scalars().all()))

    async def build_metrics(self) -> BoardMetrics:
        period = f"{self._now.year:04d}-{self._now.month:02d}"
        mrr = await self._fetch_mrr()
        arr = mrr * Decimal("12")
        burn, runway = load_burn(self._burn_path)
        runs = await self._fetch_runs_count(self._now.year, self._now.month)
        breakers = await self._fetch_breakers_tripped()
        incidents = count_incidents_in_month(
            self._incidents_dir, self._now.year, self._now.month
        )
        return BoardMetrics(
            period=period,
            mrr_eur=mrr,
            arr_eur=arr,
            burn_eur=burn,
            runway_months=runway,
            nrr_pct=None,
            runs_month=runs,
            breakers_tripped=breakers,
            incidents_month=incidents,
        )

    async def run(self) -> RunResult:
        try:
            metrics = await self.build_metrics()
        except Exception as exc:
            raise AgentDataSourceError(f"build_metrics: {exc}") from exc

        try:
            self._output_dir.mkdir(parents=True, exist_ok=True)
            output_path = self._output_dir / f"board-{metrics.period}.md"
            output_path.write_text(render_board_pack(metrics), encoding="utf-8")
        except OSError as exc:
            raise AgentOutputError(f"write board pack: {exc}") from exc
        summary = (
            f"board pack écrit dans {output_path.name} "
            f"(MRR {metrics.mrr_eur:.0f}€ · {metrics.runs_month} runs · "
            f"{metrics.incidents_month} incidents)"
        )
        return RunResult(
            status="success",
            output_summary=summary,
            extras={
                "output_path": str(output_path),
                "mrr_eur": str(metrics.mrr_eur),
                "runs_month": metrics.runs_month,
            },
        )


def build_today() -> date:
    """Helper testable — date utc du jour."""
    return datetime.now(UTC).date()


__all__ = [
    "DEFAULT_BURN_PATH",
    "DEFAULT_INCIDENTS_DIR",
    "DEFAULT_OUTPUT_DIR",
    "BoardMetrics",
    "BoardReporter",
    "build_today",
    "count_incidents_in_month",
    "load_burn",
    "render_board_pack",
]
