"""LandingOptimizer — propose des variantes A/B pour les landing.

Source des métriques (cf. :func:`collect_metrics`) : l'API Umami self-host
(INFRA-02) dès que les variables ``UMAMI_*`` sont configurées, sinon le YAML
manuel ``data/analytics/landing_perf.yaml`` en fallback (shadow mode ou
instance Umami indisponible). Le bot propose ensuite 3 hypothèses A/B
chiffrées dans ``data/analytics/landing_proposals-<date>.md``.

Critères canoniques :
- CR < 1.0 % : suggérer changement de headline (clarification proposition de valeur)
- Bounce > 70 % : suggérer ajout d'éléments de preuve (testimonial, badge, chiffre)
- Time on page < 20 s : suggérer accroche visuelle (image hero, vidéo loop)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import yaml
from loguru import logger

from argos_ops.agents.base import BaseAgent, IOItem, RunResult
from argos_ops.config import REPO_ROOT, get_settings
from argos_ops.integrations.umami import UmamiClient, UmamiPageMetric
from argos_ops.notifications.discord import GREEN, YELLOW, Embed, EmbedField, send_embed

PERF_PATH = REPO_ROOT / "data" / "analytics" / "landing_perf.yaml"
PROPOSALS_DIR = REPO_ROOT / "data" / "analytics"


@dataclass
class LandingMetric:
    page: str
    visits: int
    conversions: int
    bounce_rate: float  # 0.0-1.0
    avg_time_seconds: float

    @property
    def conversion_rate(self) -> float:
        if self.visits == 0:
            return 0.0
        return self.conversions / self.visits


@dataclass
class Proposal:
    page: str
    issue: str
    hypothesis: str


@dataclass
class OptimizationReport:
    metrics: list[LandingMetric]
    proposals: list[Proposal] = field(default_factory=list)
    digest_path: Path | None = None

    @property
    def has_signal(self) -> bool:
        return len(self.proposals) > 0

    def summary(self) -> str:
        return f"pages={len(self.metrics)} proposals={len(self.proposals)}"


def load_metrics(path: Path | None = None) -> list[LandingMetric]:
    path = path or PERF_PATH
    if not path.exists():
        return []
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    out: list[LandingMetric] = []
    required = ("visits", "conversions", "bounce_rate", "avg_time_seconds")
    for entry in raw.get("pages", []):
        if not isinstance(entry, dict):
            continue
        if "page" not in entry or any(k not in entry for k in required):
            continue
        try:
            out.append(
                LandingMetric(
                    page=str(entry["page"]),
                    visits=int(entry["visits"]),
                    conversions=int(entry["conversions"]),
                    bounce_rate=float(entry["bounce_rate"]),
                    avg_time_seconds=float(entry["avg_time_seconds"]),
                )
            )
        except (ValueError, TypeError):
            continue
    return out


def _metric_from_umami(u: UmamiPageMetric) -> LandingMetric:
    """Convertit le DTO intégration en DTO agent (champs alignés 1:1)."""
    return LandingMetric(
        page=u.page,
        visits=u.visits,
        conversions=u.conversions,
        bounce_rate=u.bounce_rate,
        avg_time_seconds=u.avg_time_seconds,
    )


async def collect_metrics(client: UmamiClient | None = None) -> list[LandingMetric]:
    """Source des métriques landing : Umami si configuré, sinon YAML manuel.

    Umami (INFRA-02) devient la source canonique dès que les 4 variables
    ``UMAMI_*`` sont présentes. Le YAML ``landing_perf.yaml`` reste un
    fallback : actif en shadow mode, et filet de sécurité si l'instance
    Umami est indisponible — un bot best-effort ne doit pas échouer sur une
    dépendance réseau optionnelle.
    """
    client = client or UmamiClient.from_settings(get_settings())
    if client.is_configured:
        try:
            umami_metrics = await client.fetch_landing_metrics()
        except Exception as exc:  # défensif : fetch ne lève pas, mais on blinde
            logger.warning(f"LandingOptimizer — Umami indisponible ({exc}), fallback YAML")
            umami_metrics = []
        if umami_metrics:
            return [_metric_from_umami(m) for m in umami_metrics]
        logger.info("LandingOptimizer — Umami configuré mais 0 page, fallback YAML")
    return load_metrics()


def derive_proposals(metrics: list[LandingMetric]) -> list[Proposal]:
    out: list[Proposal] = []
    for m in metrics:
        if m.conversion_rate < 0.01 and m.visits >= 100:
            out.append(
                Proposal(
                    page=m.page,
                    issue=f"CR {m.conversion_rate * 100:.2f}% < 1%",
                    hypothesis="Réécrire le headline pour clarifier la proposition de valeur en < 8 mots.",
                )
            )
        if m.bounce_rate > 0.70:
            out.append(
                Proposal(
                    page=m.page,
                    issue=f"Bounce {m.bounce_rate * 100:.0f}% > 70%",
                    hypothesis="Ajouter 1 testimonial chiffré + 1 badge confiance au-dessus du fold.",
                )
            )
        if m.avg_time_seconds < 20.0 and m.visits >= 50:
            out.append(
                Proposal(
                    page=m.page,
                    issue=f"Time on page {m.avg_time_seconds:.0f}s < 20s",
                    hypothesis="Remplacer le bloc hero texte par image/loop animé du scan Argos en action.",
                )
            )
    return out


def write_proposals_digest(report: OptimizationReport, *, now: datetime | None = None) -> Path:
    now = now or datetime.now(UTC)
    PROPOSALS_DIR.mkdir(parents=True, exist_ok=True)
    path = PROPOSALS_DIR / f"landing_proposals-{now.date().isoformat()}.md"
    lines = [f"# LandingOptimizer — {now.date()}", "", "## Pages analysées"]
    for m in report.metrics:
        lines.append(
            f"- **{m.page}** : {m.visits} visites · CR {m.conversion_rate * 100:.2f}% "
            f"· bounce {m.bounce_rate * 100:.0f}% · time {m.avg_time_seconds:.0f}s"
        )
    if report.proposals:
        lines.extend(["", "## Hypothèses A/B"])
        for p in report.proposals:
            lines.append(f"### {p.page} — {p.issue}")
            lines.append(p.hypothesis)
            lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def build_optimizer_embed(report: OptimizationReport) -> Embed:
    color = YELLOW if report.has_signal else GREEN
    return Embed(
        title="Argos — LandingOptimizer",
        color=color,
        fields=[
            EmbedField(name="Pages analysées", value=str(len(report.metrics)), inline=True),
            EmbedField(name="Hypothèses A/B", value=str(len(report.proposals)), inline=True),
        ],
        footer="Argos Ops • LandingOptimizer",
    )


class LandingOptimizer(BaseAgent):
    """Propose des variantes A/B basées sur les métriques de landing."""

    name = "LandingOptimizer"
    command = "/run-landing-optim"
    breaker_name = "LandingOptimizer"
    ai_act_risk_class = "minimal"

    async def run(self) -> RunResult:
        metrics = await collect_metrics()
        proposals = derive_proposals(metrics)
        report = OptimizationReport(metrics=metrics, proposals=proposals)

        if metrics:
            report.digest_path = write_proposals_digest(report)

        settings = get_settings()
        webhook = settings.discord_webhook_content or settings.discord_webhook_ops_logs
        if webhook is not None and report.has_signal:
            try:
                await send_embed(webhook, build_optimizer_embed(report))
            except Exception as exc:
                logger.warning(f"LandingOptimizer — notif Discord a échoué : {exc}")

        def _rel(p: Path) -> str:
            try:
                return p.relative_to(REPO_ROOT).as_posix()
            except ValueError:
                return str(p)

        inputs = [
            IOItem(
                label="Métriques landing pages",
                kind="api",
                detail="Umami (INFRA-02) ou fallback data/analytics/landing_perf.yaml",
                ref=_rel(PERF_PATH),
                count=len(metrics),
            )
        ]
        outputs: list[IOItem] = []
        if report.digest_path is not None:
            outputs.append(
                IOItem(
                    label="Hypothèses A/B chiffrées",
                    kind="file",
                    detail=f"{len(report.proposals)} proposition(s)",
                    ref=_rel(report.digest_path),
                    count=len(report.proposals),
                )
            )

        return RunResult(
            status="success",
            output_summary=report.summary(),
            inputs=inputs,
            outputs=outputs,
        )


__all__ = [
    "PERF_PATH",
    "PROPOSALS_DIR",
    "LandingMetric",
    "LandingOptimizer",
    "OptimizationReport",
    "Proposal",
    "build_optimizer_embed",
    "collect_metrics",
    "derive_proposals",
    "load_metrics",
    "write_proposals_digest",
]
