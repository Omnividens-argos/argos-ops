"""OKRTracker — Chief of Staff (P22.E Direction Sprint 9).

Lit ``data/okr/YYYY-Qn.yaml`` (OKRs trimestriels) et calcule le progrès
de chaque key result vs sa cible. Source des actuals : sum/count sur
``agent_runs`` ou champs explicites dans le YAML (mode dev sans DB).

Politique :
- **Silence** Discord si tous les KRs sont ≥ on-track (progrès ≥
  prorata temporis)
- **Embed jaune** si ≥1 KR ``at_risk`` (progrès 50-90% du prorata)
- **Embed rouge** si ≥1 KR ``off_track`` (progrès < 50% du prorata)

Cf. plan ``docs/ARGOS_OPS_PLAN.md`` Annexe D § 1 Direction, Sprint 9.
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

DEFAULT_OKR_DIR: Path = REPO_ROOT / "data" / "okr"

KRStatus = Literal["on_track", "at_risk", "off_track", "completed"]


@dataclass(frozen=True)
class KeyResult:
    """Un Key Result + sa progression."""

    objective: str
    name: str
    target: float
    actual: float
    unit: str
    status: KRStatus
    progress_pct: float
    expected_pct: float  # prorata temporis


@dataclass(frozen=True)
class OKRReport:
    """Résultat agrégé du run OKRTracker."""

    quarter: str
    key_results: list[KeyResult]
    should_alert: bool
    alert_color: int
    summary: str


# =============================================================================
# Prorata temporis
# =============================================================================
_QUARTER_BOUNDS: dict[int, tuple[int, int, int, int]] = {
    # quarter → (start_month, start_day, end_month, end_day)
    1: (1, 1, 3, 31),
    2: (4, 1, 6, 30),
    3: (7, 1, 9, 30),
    4: (10, 1, 12, 31),
}


def quarter_bounds(year: int, quarter: int) -> tuple[date, date]:
    """Retourne ``(start, end)`` du trimestre."""
    if quarter not in _QUARTER_BOUNDS:
        raise ValueError(f"quarter invalide: {quarter}")
    sm, sd, em, ed = _QUARTER_BOUNDS[quarter]
    return date(year, sm, sd), date(year, em, ed)


def prorata(today: date, *, year: int, quarter: int) -> float:
    """Pourcentage du trimestre écoulé (clamp 0..1)."""
    start, end = quarter_bounds(year, quarter)
    if today <= start:
        return 0.0
    if today >= end:
        return 1.0
    elapsed = (today - start).days
    total = (end - start).days
    return elapsed / total if total > 0 else 0.0


def classify(progress: float, expected: float) -> KRStatus:
    """Compare la progression actuelle au prorata temporis."""
    if progress >= 1.0:
        return "completed"
    # Au début du trimestre, ne pas pénaliser tant que l'expected < 5%
    if expected < 0.05:
        return "on_track"
    ratio = progress / expected
    if ratio >= 0.9:
        return "on_track"
    if ratio >= 0.5:
        return "at_risk"
    return "off_track"


# =============================================================================
# Lecture YAML
# =============================================================================
def load_okr(path: Path, *, today: date | None = None) -> OKRReport:
    """Lit le YAML OKR et calcule les statuts.

    Format YAML attendu ::

        quarter: 2026-Q2
        year: 2026
        objectives:
          - title: "Atteindre 10k€ MRR"
            key_results:
              - name: "MRR fin de trimestre"
                target: 10000
                actual: 4200
                unit: "EUR"
    """
    today = today or datetime.now(UTC).date()
    if not path.exists():
        return OKRReport(
            quarter="<missing>",
            key_results=[],
            should_alert=True,
            alert_color=RED,
            summary=f"fichier OKR introuvable : {path.name}",
        )
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    quarter_label = str(raw.get("quarter", "?"))
    year = int(raw.get("year", today.year))
    quarter_num = int(raw.get("quarter_num", _detect_quarter(quarter_label, today.month)))
    expected = prorata(today, year=year, quarter=quarter_num)

    krs: list[KeyResult] = []
    for obj in raw.get("objectives", []) or []:
        obj_title = obj.get("title") or ""
        for kr in obj.get("key_results", []) or []:
            target = float(kr.get("target", 0))
            actual = float(kr.get("actual", 0))
            if target <= 0:
                continue
            progress = actual / target
            krs.append(
                KeyResult(
                    objective=obj_title,
                    name=str(kr.get("name", "?")),
                    target=target,
                    actual=actual,
                    unit=str(kr.get("unit", "")),
                    status=classify(progress, expected),
                    progress_pct=progress,
                    expected_pct=expected,
                )
            )

    return build_report(krs, quarter=quarter_label)


def _detect_quarter(label: str, fallback_month: int) -> int:
    """Extrait ``Q1`` / ``Q2`` / ``Q3`` / ``Q4`` du label, sinon fallback mois."""
    for q in (1, 2, 3, 4):
        if f"Q{q}" in label.upper():
            return q
    if 1 <= fallback_month <= 3:
        return 1
    if 4 <= fallback_month <= 6:
        return 2
    if 7 <= fallback_month <= 9:
        return 3
    return 4


# =============================================================================
# Décision
# =============================================================================
def build_report(krs: list[KeyResult], *, quarter: str) -> OKRReport:
    has_off = any(k.status == "off_track" for k in krs)
    has_risk = any(k.status == "at_risk" for k in krs)
    should_alert = has_off or has_risk

    if has_off:
        alert_color = RED
    elif has_risk:
        alert_color = YELLOW
    else:
        alert_color = GREEN

    counts = {
        s: sum(1 for k in krs if k.status == s)
        for s in ("on_track", "at_risk", "off_track", "completed")
    }
    summary = (
        f"{counts['on_track']} on track · {counts['at_risk']} at risk · "
        f"{counts['off_track']} off track · {counts['completed']} done"
    )
    return OKRReport(
        quarter=quarter,
        key_results=krs,
        should_alert=should_alert,
        alert_color=alert_color,
        summary=summary,
    )


# =============================================================================
# Formatting
# =============================================================================
_STATUS_ICON: dict[KRStatus, str] = {
    "on_track": "[OK]",
    "at_risk": "[RSK]",
    "off_track": "[OFF]",
    "completed": "[DONE]",
}


def build_okr_embed(report: OKRReport, *, now: datetime | None = None) -> Embed:
    """Embed Discord — un field par KR at_risk/off_track."""
    now = now or datetime.now(UTC)
    flagged = [k for k in report.key_results if k.status in ("at_risk", "off_track")]
    fields = [
        EmbedField(
            name=f"{_STATUS_ICON[k.status]} {k.name}",
            value=(
                f"{k.actual:.0f} / {k.target:.0f} {k.unit} "
                f"({k.progress_pct * 100:.0f}% vs expected {k.expected_pct * 100:.0f}%)"
            ),
            inline=False,
        )
        for k in flagged[:15]
    ]
    title_status = color_title(report.alert_color, green=GREEN, yellow=YELLOW, red=RED)
    return Embed(
        title=f"OKRTracker {report.quarter} — {title_status}",
        description=report.summary,
        color=report.alert_color,
        fields=fields,
        footer="Argos Ops • OKRTracker",
        timestamp=now.isoformat(),
    )


# =============================================================================
# Agent
# =============================================================================
class OKRTracker(BaseAgent):
    """Chief of Staff — suivi OKRs trimestriels."""

    name = "OKRTracker"
    command = "/run-okr-review"
    breaker_name = None
    ai_act_risk_class = "minimal"

    def __init__(
        self,
        *,
        okr_dir: Path = DEFAULT_OKR_DIR,
        okr_file: str | None = None,
        today: date | None = None,
    ) -> None:
        self._okr_dir = okr_dir
        self._explicit_file = okr_file
        self._today = today or datetime.now(UTC).date()

    def _resolve_path(self) -> Path:
        if self._explicit_file is not None:
            return self._okr_dir / self._explicit_file
        # Convention : YYYY-Qn.yaml selon date courante
        q = _detect_quarter("", self._today.month)
        return self._okr_dir / f"{self._today.year}-Q{q}.yaml"

    async def run(self) -> RunResult:
        path = self._resolve_path()
        report = load_okr(path, today=self._today)
        return await emit_alert_or_silence(
            report, embed_builder=build_okr_embed, agent_name=self.name
        )


__all__ = [
    "DEFAULT_OKR_DIR",
    "KRStatus",
    "KeyResult",
    "OKRReport",
    "OKRTracker",
    "build_okr_embed",
    "build_report",
    "classify",
    "load_okr",
    "prorata",
    "quarter_bounds",
]
