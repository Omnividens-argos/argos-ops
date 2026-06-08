"""KeywordRadar — surveille positions SERP + opportunités longue traîne.

Mode shadow (Sprint 12) : pas de scraping SERP automatique. Le founder
(ou un futur connecteur GSC) maintient ``data/seo/keywords_tracked.yaml``
qui liste les keywords + leur position actuelle. Le bot :

1. Lit le YAML, garde les keywords avec ``priority: high``
2. Compare aux positions précédentes archivées dans
   ``data/seo/ranks_history.yaml``
3. Écrit un mouvement ``data/seo/movements-<date>.md`` (top 5 montées /
   descentes / nouvelles longue traîne)
4. Alerte Discord (jaune) si ≥ 3 keywords ont perdu > 5 positions
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import yaml
from loguru import logger

from argos_ops.agents.base import BaseAgent, IOItem, RunResult
from argos_ops.config import REPO_ROOT, get_settings
from argos_ops.notifications.discord import GREEN, YELLOW, Embed, EmbedField, send_embed

KEYWORDS_PATH = REPO_ROOT / "data" / "seo" / "keywords_tracked.yaml"
HISTORY_PATH = REPO_ROOT / "data" / "seo" / "ranks_history.yaml"
MOVEMENTS_DIR = REPO_ROOT / "data" / "seo"


@dataclass
class KeywordMovement:
    keyword: str
    current: int
    previous: int | None

    @property
    def delta(self) -> int:
        if self.previous is None:
            return 0
        return self.previous - self.current  # positif = on est monté

    @property
    def is_new(self) -> bool:
        return self.previous is None


@dataclass
class RadarReport:
    movements: list[KeywordMovement]
    digest_path: Path | None = None
    losses_over_5: int = field(init=False, default=0)

    def __post_init__(self) -> None:
        self.losses_over_5 = sum(1 for m in self.movements if m.delta <= -5)

    @property
    def should_alert(self) -> bool:
        return self.losses_over_5 >= 3

    def summary(self) -> str:
        ups = sum(1 for m in self.movements if m.delta > 0)
        downs = sum(1 for m in self.movements if m.delta < 0)
        return f"keywords={len(self.movements)} up={ups} down={downs} losses5+={self.losses_over_5}"


def load_keywords(path: Path | None = None) -> dict[str, int]:
    path = path or KEYWORDS_PATH
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    out: dict[str, int] = {}
    for entry in data.get("keywords", []):
        if not isinstance(entry, dict):
            continue
        if str(entry.get("priority", "")).lower() != "high":
            continue
        kw = str(entry.get("term", "")).strip()
        pos = entry.get("position")
        if not kw or not isinstance(pos, int):
            continue
        out[kw] = pos
    return out


def load_history(path: Path | None = None) -> dict[str, int]:
    path = path or HISTORY_PATH
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return {str(k): int(v) for k, v in data.get("positions", {}).items() if isinstance(v, int)}


def save_history(positions: dict[str, int], path: Path | None = None) -> None:
    path = path or HISTORY_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump({"positions": positions}), encoding="utf-8")


def diff_positions(current: dict[str, int], previous: dict[str, int]) -> list[KeywordMovement]:
    movements: list[KeywordMovement] = []
    for kw, pos in current.items():
        movements.append(KeywordMovement(keyword=kw, current=pos, previous=previous.get(kw)))
    return movements


def write_movements_digest(report: RadarReport, *, now: datetime | None = None) -> Path:
    now = now or datetime.now(UTC)
    MOVEMENTS_DIR.mkdir(parents=True, exist_ok=True)
    path = MOVEMENTS_DIR / f"movements-{now.date().isoformat()}.md"
    movements_sorted = sorted(report.movements, key=lambda m: m.delta, reverse=True)
    lines = [f"# KeywordRadar — {now.date()}", "", "## Top 5 montées"]
    for m in [x for x in movements_sorted if x.delta > 0][:5]:
        lines.append(f"- **{m.keyword}** : {m.previous} → {m.current} (+{m.delta})")
    lines.extend(["", "## Top 5 descentes"])
    for m in [x for x in movements_sorted if x.delta < 0][-5:][::-1]:
        lines.append(f"- **{m.keyword}** : {m.previous} → {m.current} ({m.delta})")
    new_kws = [m for m in report.movements if m.is_new]
    if new_kws:
        lines.extend(["", "## Nouveaux keywords"])
        for m in new_kws:
            lines.append(f"- **{m.keyword}** : pos {m.current}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def build_radar_embed(report: RadarReport) -> Embed:
    color = YELLOW if report.should_alert else GREEN
    return Embed(
        title="Argos — KeywordRadar",
        color=color,
        fields=[
            EmbedField(name="Keywords trackés", value=str(len(report.movements)), inline=True),
            EmbedField(
                name="Pertes > 5 pos",
                value=str(report.losses_over_5),
                inline=True,
            ),
        ],
        footer="Argos Ops • KeywordRadar",
    )


class KeywordRadar(BaseAgent):
    """Surveille positions SERP keywords prioritaires."""

    name = "KeywordRadar"
    command = "/run-keyword-radar"
    breaker_name = "KeywordRadar"
    ai_act_risk_class = "minimal"

    async def run(self) -> RunResult:
        current = load_keywords()
        previous = load_history()
        movements = diff_positions(current, previous)
        report = RadarReport(movements=movements)

        if current:
            report.digest_path = write_movements_digest(report)
            save_history(current)

        settings = get_settings()
        webhook = settings.discord_webhook_content or settings.discord_webhook_ops_logs
        if webhook is not None and (report.should_alert or movements):
            try:
                await send_embed(webhook, build_radar_embed(report))
            except Exception as exc:
                logger.warning(f"KeywordRadar — notif Discord a échoué : {exc}")

        def _rel(p: Path) -> str:
            try:
                return p.relative_to(REPO_ROOT).as_posix()
            except ValueError:
                return str(p)

        inputs = [
            IOItem(
                label="Keywords prioritaires trackés",
                kind="file",
                detail="positions SERP courantes (priority: high)",
                ref=_rel(KEYWORDS_PATH),
                count=len(current),
            ),
            IOItem(
                label="Historique positions",
                kind="file",
                detail="positions du run précédent",
                ref=_rel(HISTORY_PATH),
                count=len(previous),
            ),
        ]
        outputs: list[IOItem] = []
        if report.digest_path is not None:
            outputs.append(
                IOItem(
                    label="Digest mouvements SERP",
                    kind="file",
                    detail=f"{report.losses_over_5} perte(s) > 5 positions",
                    ref=_rel(report.digest_path),
                    count=len(movements),
                )
            )

        return RunResult(
            status="success",
            output_summary=report.summary(),
            inputs=inputs,
            outputs=outputs,
        )


__all__ = [
    "HISTORY_PATH",
    "KEYWORDS_PATH",
    "MOVEMENTS_DIR",
    "KeywordMovement",
    "KeywordRadar",
    "RadarReport",
    "build_radar_embed",
    "diff_positions",
    "load_history",
    "load_keywords",
    "save_history",
    "write_movements_digest",
]
