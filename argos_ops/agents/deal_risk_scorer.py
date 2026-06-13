"""DealRiskScorer — Sales Manager (P22.H Sales Sprint 3, cerveau Axe 2).

Lit le pipe ``data/sales/deals/pipe.yaml`` (saisi à la main par le
fondateur, mis à jour après chaque interaction client) et score chaque
deal via :func:`argos_ops.sales.scoring.score_deal_risk`. Discord
notification résumant les deals stalled + top 3 par risk_score.

Format YAML attendu ::

    deals:
      - deal_id: "acme-q2-2026"
        company: "Acme SA"
        stage: "demo_done"  # discovery|demo_scheduled|demo_done|proposal_sent|contract_sent|won|lost
        amount_eur: 4200
        last_activity_at: 2026-05-10
        owner: "founder"
        notes: "Marc revient mardi avec son board"

Cerveau (Axe 2) : le **score reste 100 % heuristique** (points explicites,
auditable — cf. ``sales/scoring.py``). Le cerveau ajoute, pour chaque deal
du top risque, une ``recommended_action`` : UNE relance concrète sous 48h
qui **exploite les notes texte libre** du deal (que l'heuristique ignore)
+ le stade + l'inactivité. Validée côté Python (longueur, deal_id connu),
jamais d'engagement chiffré. Cerveau OFF/HS → embed sans actions, comme
avant.

Aucune écriture sur le YAML — read-only. Le bot loggue + alerte Discord.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import yaml
from loguru import logger

from argos_ops.agents.base import BaseAgent, IOItem, RunResult
from argos_ops.brain import BrainEngine, think_json
from argos_ops.config import REPO_ROOT, get_settings
from argos_ops.notifications.discord import (
    GREEN,
    ORANGE,
    YELLOW,
    Embed,
    EmbedField,
    send_embed,
)
from argos_ops.sales.models import Deal, DealStage, DealStalledFlag
from argos_ops.sales.scoring import score_deal_risk

DEFAULT_PIPE_PATH: Path = REPO_ROOT / "data" / "sales" / "deals" / "pipe.yaml"

# Cerveau : bornes de validation d'une action recommandée.
ACTION_MIN_CHARS = 20
ACTION_MAX_CHARS = 220
_NOTES_EXCERPT_CHARS = 300

# Une action recommandée par deal_id.
BrainActionMap = dict[str, str]


@dataclass
class DealReport:
    """Récap d'un run."""

    total: int = 0
    active: int = 0
    won: int = 0
    lost: int = 0
    stalled: int = 0
    top_risk: list[DealStalledFlag] = field(default_factory=list)

    def summary(self) -> str:
        return (
            f"total={self.total} active={self.active} stalled={self.stalled} "
            f"won={self.won} lost={self.lost}"
        )


def _load_pipe(path: Path) -> list[Deal]:
    if not path.exists():
        return []
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    deals_raw = raw.get("deals", [])
    out: list[Deal] = []
    for entry in deals_raw:
        last_raw = entry["last_activity_at"]
        last = last_raw if isinstance(last_raw, date) else date.fromisoformat(str(last_raw))
        stage = DealStage(entry["stage"])
        out.append(
            Deal(
                deal_id=entry["deal_id"],
                company=entry["company"],
                stage=stage,
                amount_eur=int(entry.get("amount_eur", 0)),
                last_activity_at=last,
                owner=entry.get("owner", "founder"),
                notes=entry.get("notes"),
            )
        )
    return out


def build_risk_report(deals: list[Deal], *, today: date | None = None) -> DealReport:
    report = DealReport(total=len(deals))
    flags: list[DealStalledFlag] = []
    for deal in deals:
        if deal.stage == DealStage.WON:
            report.won += 1
            continue
        if deal.stage == DealStage.LOST:
            report.lost += 1
            continue
        report.active += 1
        flag = score_deal_risk(deal, today=today)
        flags.append(flag)
        if flag.is_stalled:
            report.stalled += 1
    flags.sort(key=lambda f: f.risk_score, reverse=True)
    report.top_risk = flags[:3]
    return report


# =============================================================================
# Cerveau — relance recommandée par deal (propose) / score heuristique (tranche)
# =============================================================================
def build_actions_prompt(flags: list[DealStalledFlag]) -> str:
    """Prompt batch : UNE relance concrète sous 48h par deal à risque.

    Inclut les **notes texte libre** du deal (signal que le score ignore).
    """
    lines = [
        "Tu es le Sales Manager d'Argos (scanner de vulnérabilités SaaS BtoB).",
        "Pour chaque deal à risque ci-dessous, propose UNE relance concrète à",
        "faire sous 48h : quel canal, quel angle, quel prochain pas — en",
        "t'appuyant sur les NOTES et le stade du deal.",
        "",
        "Règles :",
        "- 1 à 2 phrases en français, directes, actionnables par le fondateur ;",
        "- exploite les notes (ex. « attend un devis » → envoyer le devis ;",
        "  « revient avec son board » → relancer après la date) ;",
        "- ne promets RIEN de chiffré (remise, délai) et n'invente aucun fait",
        "  qui n'est pas dans les notes ;",
        "- proposal_sent stalled → relancer la décision ; demo_done stalled →",
        "  envoyer la prochaine étape concrète ; contract_sent → suivre la",
        "  signature sans presser.",
        "",
        "Réponds UNIQUEMENT avec un objet JSON strict de la forme :",
        '{"actions": [{"deal_id": "...", "action": "..."}]}',
        "",
        "Deals à risque :",
        "",
    ]
    for flag in flags:
        deal = flag.deal
        notes = " ".join((deal.notes or "—").split())[:_NOTES_EXCERPT_CHARS]
        lines.append(
            f"- deal_id: {deal.deal_id} | société: {deal.company} | "
            f"stade: {deal.stage.value} | inactif: {flag.days_since_activity}j | "
            f"montant: {deal.amount_eur}€/mois | risk: {flag.risk_score}/100"
        )
        lines.append(f"  notes: {notes}")
    return "\n".join(lines)


def parse_brain_actions(data: dict[str, object], *, known_ids: set[str]) -> BrainActionMap:
    """Valide les relances proposées — deal_id inconnu / hors bornes = ignorée."""
    out: BrainActionMap = {}
    raw = data.get("actions")
    if not isinstance(raw, list):
        return out
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        deal_id = str(entry.get("deal_id", ""))
        action = " ".join(str(entry.get("action", "")).split())
        if deal_id not in known_ids:
            continue
        if not (ACTION_MIN_CHARS <= len(action) <= ACTION_MAX_CHARS):
            logger.warning(
                f"DealRiskScorer — action cerveau hors bornes pour {deal_id} "
                f"({len(action)} chars), ignorée"
            )
            continue
        out[deal_id] = action
    return out


async def recommend_actions(
    flags: list[DealStalledFlag],
) -> tuple[BrainActionMap, BrainEngine]:
    """Demande au cerveau une relance par deal à risque. Map vide = sans actions."""
    if not flags:
        return {}, "disabled"
    answer = await think_json(build_actions_prompt(flags))
    if not answer.ok or answer.data is None:
        return {}, answer.engine
    known = {flag.deal.deal_id for flag in flags}
    return parse_brain_actions(answer.data, known_ids=known), answer.engine


def build_risk_embed(report: DealReport, *, actions: BrainActionMap | None = None) -> Embed:
    actions = actions or {}
    if report.stalled > 0:
        color = ORANGE
    elif report.active > 0:
        color = YELLOW
    else:
        color = GREEN
    fields = [
        EmbedField(name="Total deals", value=str(report.total), inline=True),
        EmbedField(name="Actifs", value=str(report.active), inline=True),
        EmbedField(name="Stalled", value=str(report.stalled), inline=True),
        EmbedField(name="Won", value=str(report.won), inline=True),
        EmbedField(name="Lost", value=str(report.lost), inline=True),
    ]
    if report.top_risk:
        lines = []
        for flag in report.top_risk:
            line = (
                f"• [{flag.risk_score}/100] **{flag.deal.company}** "
                f"({flag.deal.stage.value}) — {flag.reason}"
            )
            action = actions.get(flag.deal.deal_id)
            if action:
                line += f"\n  → {action}"
            lines.append(line)
        fields.append(EmbedField(name="Top risque", value="\n".join(lines), inline=False))
    return Embed(
        title=f"DealRiskScorer — {report.stalled} stalled / {report.active} actifs",
        description=(
            "Relance les deals stalled prioritairement (top risque ci-dessous)."
            if report.stalled > 0
            else "Pipe propre, aucun deal stalled au-delà du seuil."
        ),
        color=color,
        fields=fields,
        footer="Argos Ops • DealRiskScorer",
    )


class DealRiskScorer(BaseAgent):
    """Score le pipe + flag les deals stalled > seuil par stade."""

    name = "DealRiskScorer"
    command = "/run-deal-scoring"
    breaker_name = "DealRiskScorer"
    ai_act_risk_class = "minimal"

    def __init__(self, *, pipe_path: Path = DEFAULT_PIPE_PATH) -> None:
        self._pipe_path = pipe_path

    async def run(self) -> RunResult:
        settings = get_settings()
        deals = _load_pipe(self._pipe_path)
        if not deals:
            logger.info(f"DealRiskScorer — pipe vide ({self._pipe_path})")
            return RunResult(status="success", output_summary="silence (no deals)")

        report = build_risk_report(deals)

        # Cerveau : relance recommandée pour les deals affichés (top risque).
        actions, engine = await recommend_actions(report.top_risk)
        if engine == "claude":
            logger.info(
                f"DealRiskScorer — cerveau claude : {len(actions)} relance(s) recommandée(s)"
            )

        webhook = settings.discord_webhook_ops_logs or settings.discord_webhook_alerts
        if webhook is not None:
            try:
                await send_embed(webhook, build_risk_embed(report, actions=actions))
            except Exception as exc:
                logger.warning(f"DealRiskScorer — notif Discord échouée : {exc}")

        inputs = [
            IOItem(
                label="Pipe commercial",
                kind="file",
                detail=f"{report.active} actif(s) · {report.won} won · {report.lost} lost",
                ref="data/sales/deals/pipe.yaml",
                count=report.total,
            )
        ]
        outputs = [
            IOItem(
                label="Top 3 deals à risque sur Discord",
                kind="discord",
                detail=f"{report.stalled} deal(s) stalled au-delà du seuil",
                count=report.stalled,
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
    "DEFAULT_PIPE_PATH",
    "BrainActionMap",
    "DealReport",
    "DealRiskScorer",
    "build_actions_prompt",
    "build_risk_embed",
    "build_risk_report",
    "parse_brain_actions",
    "recommend_actions",
]
