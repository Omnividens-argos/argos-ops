"""ChurnPredictor — Retention Manager (P22.G CS Sprint 7, cerveau Axe 2).

Détecte les signaux pré-churn et calcule un ``risk_score`` 0-100 par
compte via ``argos_ops.cs.scoring.detect_churn_signals``. Écrit
``data/churn/at_risk_<YYYY-MM-DD>.yaml`` + Discord rouge si ≥ 1 compte à
``risk_score ≥ 60``.

Signaux cumulatifs (déterministes, auditables — RGPD § 22) :
- inactivité (≥ 14j jaune, ≥ 30j rouge)
- NPS détracteur (≤ 6)
- tickets 30j (friction)
- sous-utilisation (< 10% du quota)

Cerveau (Axe 2) : le **score reste 100 % heuristique** (explicable client
par client) — le cerveau n'y touche pas. Il ajoute, pour chaque compte à
risque, une ``recommended_action`` : UNE action concrète sous 48h (qui
contacter, quel angle), dérivée des signaux. Validée côté Python
(longueur, id connu), jamais d'engagement chiffré. Cerveau OFF/HS → le
snapshot sort sans actions, comme avant.

Le founder traite à la main : appel proactif au compte ≥ 60, mail
empathique au compte 30-60. Idempotent.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

import yaml
from loguru import logger

from argos_ops.agents.base import BaseAgent, IOItem, RunResult
from argos_ops.brain import BrainEngine, think_json
from argos_ops.config import REPO_ROOT, get_settings
from argos_ops.cs.loader import load_customers
from argos_ops.cs.models import ChurnSignal
from argos_ops.cs.scoring import detect_churn_signals
from argos_ops.notifications.discord import (
    GREEN,
    RED,
    YELLOW,
    Embed,
    EmbedField,
    send_embed,
)

DEFAULT_CUSTOMERS_PATH: Path = REPO_ROOT / "data" / "cs" / "customers.yaml"
DEFAULT_SNAPSHOTS_DIR: Path = REPO_ROOT / "data" / "churn"

URGENT_RISK_THRESHOLD = 60  # score ≥ 60 → action proactive sous 48h

# Cerveau : bornes de validation d'une action recommandée.
BRAIN_BATCH_MAX = 10
ACTION_MIN_CHARS = 20
ACTION_MAX_CHARS = 220

# Une action recommandée par customer_id.
BrainActionMap = dict[str, str]


@dataclass
class ChurnReport:
    customers_seen: int = 0
    at_risk: list[ChurnSignal] = field(default_factory=list)
    urgent: list[ChurnSignal] = field(default_factory=list)

    def summary(self) -> str:
        return (
            f"customers={self.customers_seen} at_risk={len(self.at_risk)} urgent={len(self.urgent)}"
        )


# =============================================================================
# Cerveau — action recommandée par compte (propose) / score heuristique (tranche)
# =============================================================================
def build_actions_prompt(signals: list[ChurnSignal]) -> str:
    """Prompt batch : UNE action concrète sous 48h par compte à risque."""
    lines = [
        "Tu es le Customer Success Lead d'Argos (scanner de vulnérabilités",
        "SaaS BtoB). Pour chaque compte à risque de churn ci-dessous, propose",
        "UNE action concrète à faire sous 48h : qui contacter, par quel canal,",
        "avec quel angle — dérivée STRICTEMENT des signaux listés.",
        "",
        "Règles :",
        "- 1 à 2 phrases en français, directes, actionnables par le fondateur ;",
        "- ne promets RIEN de chiffré (remise, geste commercial, délai",
        "  contractuel) et n'invente aucun fait sur le compte ;",
        "- inactivité → réengager sur un cas d'usage ; NPS bas → écouter en",
        "  direct ; friction tickets → suivre l'incident ; sous-utilisation →",
        "  proposer un onboarding ciblé.",
        "",
        "Réponds UNIQUEMENT avec un objet JSON strict de la forme :",
        '{"actions": [{"customer_id": "...", "action": "..."}]}',
        "",
        "Comptes à risque :",
        "",
    ]
    for s in signals:
        lines.append(f"- customer_id: {s.customer_id} | risk_score: {s.risk_score}/100")
        lines.append(f"  signaux: {'; '.join(s.signals)}")
    return "\n".join(lines)


def parse_brain_actions(data: dict[str, object], *, known_ids: set[str]) -> BrainActionMap:
    """Valide les actions proposées — id inconnu / hors bornes = ignorée."""
    out: BrainActionMap = {}
    raw = data.get("actions")
    if not isinstance(raw, list):
        return out
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        customer_id = str(entry.get("customer_id", ""))
        action = " ".join(str(entry.get("action", "")).split())
        if customer_id not in known_ids:
            continue
        if not (ACTION_MIN_CHARS <= len(action) <= ACTION_MAX_CHARS):
            logger.warning(
                f"ChurnPredictor — action cerveau hors bornes pour {customer_id} "
                f"({len(action)} chars), ignorée"
            )
            continue
        out[customer_id] = action
    return out


async def recommend_actions(
    signals: list[ChurnSignal],
) -> tuple[BrainActionMap, BrainEngine]:
    """Demande au cerveau une action par compte à risque. Map vide = sans actions."""
    if not signals:
        return {}, "disabled"
    batch = signals[:BRAIN_BATCH_MAX]
    answer = await think_json(build_actions_prompt(batch))
    if not answer.ok or answer.data is None:
        return {}, answer.engine
    return parse_brain_actions(answer.data, known_ids={s.customer_id for s in batch}), (
        answer.engine
    )


def _persist_snapshot(
    snapshot_path: Path,
    signals: list[ChurnSignal],
    *,
    day: date,
    actions: BrainActionMap | None = None,
    engine: BrainEngine = "disabled",
) -> None:
    actions = actions or {}
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = {
        "snapshot_date": day.isoformat(),
        "actions_engine": "claude" if engine == "claude" else "none",
        "at_risk": [
            {
                "customer_id": s.customer_id,
                "risk_score": s.risk_score,
                "signals": s.signals,
                **(
                    {"recommended_action": actions[s.customer_id]}
                    if s.customer_id in actions
                    else {}
                ),
            }
            for s in signals
        ],
    }
    snapshot_path.write_text(
        yaml.safe_dump(payload, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )


def build_churn_embed(report: ChurnReport, *, actions: BrainActionMap | None = None) -> Embed:
    actions = actions or {}
    if report.urgent:
        color = RED
    elif report.at_risk:
        color = YELLOW
    else:
        color = GREEN
    fields = [
        EmbedField(name="Clients vus", value=str(report.customers_seen), inline=True),
        EmbedField(name="À risque", value=str(len(report.at_risk)), inline=True),
        EmbedField(name="Urgents (≥ 60)", value=str(len(report.urgent)), inline=True),
    ]
    if report.urgent:
        lines = []
        for s in report.urgent[:5]:
            line = f"• [{s.risk_score}/100] **{s.customer_id}** — {'; '.join(s.signals[:3])}"
            action = actions.get(s.customer_id)
            if action:
                line += f"\n  → {action}"
            lines.append(line)
        fields.append(EmbedField(name="Action proactive 48h", value="\n".join(lines), inline=False))
    elif report.at_risk:
        lines = [
            f"• [{s.risk_score}/100] **{s.customer_id}** — {'; '.join(s.signals[:2])}"
            for s in report.at_risk[:5]
        ]
        fields.append(EmbedField(name="À surveiller", value="\n".join(lines), inline=False))
    return Embed(
        title=f"ChurnPredictor — {len(report.urgent)} urgent / {len(report.at_risk)} à risque",
        description=(
            "Appel proactif sous 48h sur les urgents — snapshot `data/churn/at_risk_<date>.yaml`."
            if report.urgent
            else (
                "Comptes à surveiller — pas d'urgence immédiate."
                if report.at_risk
                else "Aucun signal pré-churn détecté."
            )
        ),
        color=color,
        fields=fields,
        footer="Argos Ops • ChurnPredictor",
    )


class ChurnPredictor(BaseAgent):
    """Détecte les signaux pré-churn et score 0-100 chaque compte à risque."""

    name = "ChurnPredictor"
    command = "/run-churn-predict"
    breaker_name = "ChurnPredictor"
    ai_act_risk_class = "minimal"

    def __init__(
        self,
        *,
        customers_path: Path = DEFAULT_CUSTOMERS_PATH,
        snapshots_dir: Path = DEFAULT_SNAPSHOTS_DIR,
    ) -> None:
        self._customers_path = customers_path
        self._snapshots_dir = snapshots_dir

    async def run(self) -> RunResult:
        settings = get_settings()
        customers = load_customers(self._customers_path)
        if not customers:
            logger.info(f"ChurnPredictor — aucun client ({self._customers_path})")
            return RunResult(status="success", output_summary="silence (no customers)")

        signals = [s for s in (detect_churn_signals(c) for c in customers) if s is not None]
        signals.sort(key=lambda s: s.risk_score, reverse=True)
        urgent = [s for s in signals if s.risk_score >= URGENT_RISK_THRESHOLD]
        report = ChurnReport(customers_seen=len(customers), at_risk=signals, urgent=urgent)

        actions, engine = await recommend_actions(signals)
        if engine == "claude":
            logger.info(
                f"ChurnPredictor — cerveau claude : {len(actions)} action(s) recommandée(s)"
            )

        today = date.today()
        snapshot_path = self._snapshots_dir / f"at_risk_{today.isoformat()}.yaml"
        _persist_snapshot(snapshot_path, signals, day=today, actions=actions, engine=engine)

        webhook = settings.discord_webhook_ops_logs or settings.discord_webhook_alerts
        if webhook is not None and signals:
            try:
                await send_embed(webhook, build_churn_embed(report, actions=actions))
            except Exception as exc:
                logger.warning(f"ChurnPredictor — notif Discord échouée : {exc}")

        def _rel(p: Path) -> str:
            try:
                return p.relative_to(REPO_ROOT).as_posix()
            except ValueError:
                return str(p)

        inputs = [
            IOItem(
                label="Comptes clients",
                kind="file",
                detail="usage · NPS · tickets · inactivité",
                ref=_rel(self._customers_path),
                count=report.customers_seen,
            )
        ]
        outputs = [
            IOItem(
                label="Snapshot comptes à risque",
                kind="file",
                detail=f"{len(urgent)} urgent(s) (score ≥ 60)",
                ref=_rel(snapshot_path),
                count=len(report.at_risk),
            )
        ]
        engine_label = "claude" if engine == "claude" else "none"
        return RunResult(
            status="success",
            output_summary=f"{report.summary()} actions={engine_label}",
            inputs=inputs,
            outputs=outputs,
        )


__all__ = [
    "ACTION_MAX_CHARS",
    "ACTION_MIN_CHARS",
    "BRAIN_BATCH_MAX",
    "DEFAULT_CUSTOMERS_PATH",
    "DEFAULT_SNAPSHOTS_DIR",
    "URGENT_RISK_THRESHOLD",
    "BrainActionMap",
    "ChurnPredictor",
    "ChurnReport",
    "build_actions_prompt",
    "build_churn_embed",
    "parse_brain_actions",
    "recommend_actions",
]
