"""Agent-juge Tier 1 (P14, D-017).

Sous D-017, le « juge » n'est pas un appel API LLM autonome : c'est
Claude Code lui-même, invoqué via le skill ``.claude/skills/claude-judge/``
depuis un slash command de drafting (``/check-emails``, ``/draft-content``,
``/generate-seo-brief``, futur ``/draft-outbound``).

Ce module fournit la plomberie Python qui encadre cet appel :

- :class:`JudgeReport` — DTO du retour structuré du juge
- :func:`parse_judge_json` — parse robuste de la sortie JSON (avec
  tolérance pour le ```json ... ``` blocks Markdown souvent rendus)
- :func:`apply_thresholds` — règles déterministes ESCALATION_RULES.md
  pour passer de (factual/tone/legal/global) → verdict canonique
- :func:`save_judge_verdict` — persistance en DB via
  :func:`argos_ops.crm.repository.add_interaction`

Pourquoi le verdict est dérivé en Python plutôt qu'écrit par le juge :
parce qu'on veut un **comportement reproductible** sur les frontières.
Le juge note, Python tranche. Si on change un seuil ESCALATION_RULES, on
ne re-prompte pas le LLM.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Literal

from sqlalchemy.ext.asyncio import AsyncSession

from argos_ops.crm.models import Interaction
from argos_ops.crm.repository import add_interaction

JudgeVerdict = Literal["auto_send", "queued", "killed"]

# ESCALATION_RULES.md (Tier 1 / Tier 2 / Tier 4) — source de vérité
AUTO_SEND_GLOBAL_MIN = 80
AUTO_SEND_FACTUAL_MIN = 70
AUTO_SEND_LEGAL_MIN = 90

QUEUED_GLOBAL_MIN = 50  # < 50 → killed
LEGAL_KILL_FLOOR = 50  # legal < 50 → killed direct (risque conformité)
FACTUAL_KILL_FLOOR = 50  # factual < 50 → killed direct (hallucination forte)


@dataclass(frozen=True)
class JudgeReport:
    """Sortie structurée du skill ``claude-judge``."""

    factual_score: int  # 0-100 — la réponse colle-t-elle aux chunks KB fournis ?
    tone_score: int  # 0-100 — alignement tone_of_voice (anti-FUD, anti-buzzword)
    legal_score: int  # 0-100 — RGPD / AI Act / Bloctel / anti-disparagement
    global_score: int  # 0-100 — agrégat pondéré (typiquement moyenne)
    rationale: str  # 1-3 phrases sur pourquoi cette note
    factual_issues: list[str] = field(default_factory=list)
    tone_issues: list[str] = field(default_factory=list)
    legal_issues: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        for axis, value in (
            ("factual_score", self.factual_score),
            ("tone_score", self.tone_score),
            ("legal_score", self.legal_score),
            ("global_score", self.global_score),
        ):
            if not 0 <= value <= 100:
                raise ValueError(f"{axis}={value!r} hors [0, 100]")


def parse_judge_json(text: str) -> JudgeReport:
    """Parse la sortie texte du juge en :class:`JudgeReport`.

    Tolère :
    - JSON brut
    - JSON enveloppé dans un bloc ``` ```json ... ``` ```
    - Texte parasite avant/après le bloc JSON

    Raise :class:`ValueError` si aucun bloc JSON parseable, ou si les
    champs requis manquent / sont mal typés.
    """
    if not text or not text.strip():
        raise ValueError("Sortie juge vide")

    # Strip ```json ... ``` si présent
    fence_match = re.search(
        r"```(?:json)?\s*\n?(\{.*?\})\s*```",
        text,
        re.DOTALL,
    )
    json_str = fence_match.group(1) if fence_match else text

    # Si pas de fence, on tente le 1er { ... } maximal du texte (best-effort)
    if not fence_match:
        first_brace = json_str.find("{")
        last_brace = json_str.rfind("}")
        if first_brace == -1 or last_brace <= first_brace:
            raise ValueError("Aucun bloc JSON trouvé dans la sortie juge")
        json_str = json_str[first_brace : last_brace + 1]

    try:
        data = json.loads(json_str)
    except json.JSONDecodeError as exc:
        raise ValueError(f"JSON invalide : {exc}") from exc

    required = {"factual_score", "tone_score", "legal_score", "global_score", "rationale"}
    missing = required - data.keys()
    if missing:
        raise ValueError(f"Champs juge manquants : {sorted(missing)}")

    return JudgeReport(
        factual_score=int(data["factual_score"]),
        tone_score=int(data["tone_score"]),
        legal_score=int(data["legal_score"]),
        global_score=int(data["global_score"]),
        rationale=str(data["rationale"]),
        factual_issues=list(data.get("factual_issues") or []),
        tone_issues=list(data.get("tone_issues") or []),
        legal_issues=list(data.get("legal_issues") or []),
    )


def apply_thresholds(report: JudgeReport) -> JudgeVerdict:
    """Tranche en ``auto_send`` / ``queued`` / ``killed`` selon ESCALATION_RULES.md.

    Ordre de priorité (kill > queued > auto_send) :

    1. ``factual_score < 50`` → ``killed`` (hallucination forte)
    2. ``legal_score < 50`` → ``killed`` (risque conformité hard)
    3. ``global_score < 50`` → ``killed`` (échec global)
    4. ``global ≥ 80 AND factual ≥ 70 AND legal ≥ 90`` → ``auto_send``
    5. Sinon → ``queued`` (file Tier 2 fondateur)
    """
    if report.factual_score < FACTUAL_KILL_FLOOR:
        return "killed"
    if report.legal_score < LEGAL_KILL_FLOOR:
        return "killed"
    if report.global_score < QUEUED_GLOBAL_MIN:
        return "killed"
    if (
        report.global_score >= AUTO_SEND_GLOBAL_MIN
        and report.factual_score >= AUTO_SEND_FACTUAL_MIN
        and report.legal_score >= AUTO_SEND_LEGAL_MIN
    ):
        return "auto_send"
    return "queued"


async def save_judge_verdict(
    session: AsyncSession,
    *,
    lead_id: int | None,
    channel: str,
    direction: str,
    agent_name: str,
    subject: str | None,
    body: str | None,
    report: JudgeReport,
    verdict: JudgeVerdict | None = None,
) -> Interaction:
    """Persiste une interaction avec le verdict du juge.

    ``verdict`` est calculé via :func:`apply_thresholds` si non fourni —
    on ne fait jamais confiance au verdict que le LLM aurait écrit
    directement dans la sortie (cf. docstring module : Python tranche).
    """
    effective_verdict: JudgeVerdict = verdict or apply_thresholds(report)
    return await add_interaction(
        session,
        lead_id=lead_id,
        channel=channel,
        direction=direction,
        agent_name=agent_name,
        subject=subject,
        body=body,
        judge_score=report.global_score,
        judge_verdict=effective_verdict,
    )


__all__ = [
    "AUTO_SEND_FACTUAL_MIN",
    "AUTO_SEND_GLOBAL_MIN",
    "AUTO_SEND_LEGAL_MIN",
    "FACTUAL_KILL_FLOOR",
    "LEGAL_KILL_FLOOR",
    "QUEUED_GLOBAL_MIN",
    "JudgeReport",
    "JudgeVerdict",
    "apply_thresholds",
    "parse_judge_json",
    "save_judge_verdict",
]
