"""Console bot — découple GÉNÉRER (réversible) de AGIR (irréversible) (Cockpit LOT 3).

Principe : aujourd'hui ``run()`` génère ET agit d'un coup. La console casse ça :

- **GÉNÉRER** (gratuit, réversible) : compose le IN (mémoire du bot + mémoire des
  bots accessibles + skills + data) → Claude Code headless (moteur atelier)
  produit un draft ET s'auto-juge (rubrique ``claude-judge``) → verdict
  déterministe via :func:`argos_ops.judge.apply_thresholds` (auto_send / queued /
  killed). **Rien n'est envoyé.**
- **AGIR** (irréversible) : déclenché APRÈS validation humaine (ou verdict très
  haut + clic explicite). Jamais par surprise.

Ce module porte les parties **pures/testables** : composition du IN,
construction du prompt de génération, parsing du draft + verdict, et la
**gâchette** (peut-on agir ?). Le streaming live réutilise le moteur atelier
(``argos_ops/ops_dashboard/atelier.py``), 100 % Claude Code Pro/Max (D-017).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from argos_ops import fleet_memory
from argos_ops.config import Settings
from argos_ops.fleet_memory import Fact
from argos_ops.judge import JudgeReport, JudgeVerdict, apply_thresholds, parse_judge_json

# Bots dont une action est réellement "live" si leur flag dédié est armé.
# Tout bot absent de cette table est considéré SHADOW par défaut (conservateur :
# le badge n'affiche jamais LIVE par erreur).
_LIVE_FLAG_BY_BOT: dict[str, str] = {
    "OutboundBot": "outbound_live_mode",
    "OutboundSender": "outbound_live_mode",
    "AdBot": "ads_live_mode",
}

# Marqueurs que le prompt demande à Claude d'émettre, pour séparer proprement le
# brouillon du bloc verdict dans la sortie.
_DRAFT_OPEN = "<<<DRAFT>>>"
_DRAFT_CLOSE = "<<<END_DRAFT>>>"


@dataclass
class InSource:
    """Une source du IN (case à cocher côté UI)."""

    key: str  # own_memory | accessible_memory | skills | data
    label: str
    count: int
    detail: str = ""


@dataclass
class InComposition:
    """Le IN composé d'un bot : sources + texte de contexte assemblé pour le LLM."""

    bot: str
    sources: list[InSource] = field(default_factory=list)
    context_text: str = ""


# =============================================================================
# Composition du IN (mémoire — file-based, testable sans DB)
# =============================================================================
def _facts_block(title: str, facts: list[Fact], limit: int = 20) -> str:
    if not facts:
        return ""
    lines = [f"## {title}"]
    for fact in facts[:limit]:
        lines.append(f"- ({fact.kind}) {fact.body}")
    return "\n".join(lines)


async def compose_in(
    bot: str,
    *,
    include_own_memory: bool = True,
    include_accessible_memory: bool = True,
    include_skills: bool = True,
    include_data: bool = True,
    skills: tuple[str, ...] = (),
    data_summary: str = "",
    root: Path = fleet_memory.FLEET_MEMORY_DIR,
) -> InComposition:
    """Assemble le IN d'un bot depuis les cases cochées.

    Mémoire propre + mémoire accessible (graphe) viennent de
    :mod:`argos_ops.fleet_memory`. ``skills`` / ``data_summary`` sont passés par
    l'appelant (le backend les tire de ``botMetadata`` / DB) — gardés en
    paramètres pour rester testable sans DB.
    """
    sources: list[InSource] = []
    blocks: list[str] = []

    if include_own_memory:
        own = await fleet_memory.read_memory(bot, root=root)
        sources.append(InSource("own_memory", "Mémoire du bot", len(own.facts)))
        block = _facts_block(f"Mémoire de {bot}", own.facts)
        if block:
            blocks.append(block)

    if include_accessible_memory:
        visible = await fleet_memory.visible_memory(bot, root=root)
        other = {b: m for b, m in visible.items() if b != bot}
        total = sum(len(m.facts) for m in other.values())
        sources.append(
            InSource(
                "accessible_memory",
                "Mémoire accessible (graphe)",
                total,
                detail=", ".join(sorted(other)) or "aucun bot accessible",
            )
        )
        for other_bot, mem in sorted(other.items()):
            block = _facts_block(f"Mémoire accessible — {other_bot}", mem.facts)
            if block:
                blocks.append(block)

    if include_skills:
        sources.append(
            InSource("skills", "Skills", len(skills), detail=", ".join(skills) or "aucun")
        )
        if skills:
            blocks.append("## Skills disponibles\n" + "\n".join(f"- {s}" for s in skills))

    if include_data:
        sources.append(InSource("data", "Données (config · KB · runs)", 0, detail=data_summary))
        if data_summary:
            blocks.append("## Données\n" + data_summary)

    return InComposition(bot=bot, sources=sources, context_text="\n\n".join(blocks))


# =============================================================================
# Prompt de génération (le LLM produit draft + verdict juge)
# =============================================================================
def build_generate_prompt(bot: str, task: str, composition: InComposition) -> str:
    """Construit le prompt headless : persona + IN + consigne + auto-jugement.

    Demande explicitement à Claude d'émettre le brouillon entre marqueurs PUIS
    un bloc JSON ``claude-judge`` (factual/tone/legal/global + rationale), pour
    un parsing déterministe ensuite (cf. :func:`parse_generation`).
    """
    ctx = composition.context_text or "(aucun contexte sélectionné)"
    return (
        f"Tu es l'agent **{bot}** de la flotte Argos Ops. Tu GÉNÈRES un brouillon, "
        "tu ne l'envoies PAS (étape réversible).\n\n"
        f"# Contexte (IN)\n{ctx}\n\n"
        f"# Consigne\n{task}\n\n"
        "# Sortie attendue (format STRICT)\n"
        f"1. Le brouillon, entre {_DRAFT_OPEN} et {_DRAFT_CLOSE}.\n"
        "2. Puis, en te jugeant toi-même selon la rubrique claude-judge "
        "(anti-hallucination, anti-FUD, RGPD/AI Act), un bloc ```json``` avec les "
        "clés : factual_score, tone_score, legal_score, global_score (0-100), "
        "rationale, et listes factual_issues / tone_issues / legal_issues.\n"
        "Sois honnête sur les scores — c'est Python qui tranche le verdict, pas toi."
    )


@dataclass(frozen=True)
class GenerationResult:
    """Résultat parsé d'une génération : brouillon + rapport juge + verdict."""

    draft: str
    report: JudgeReport
    verdict: JudgeVerdict


def parse_generation(output_text: str) -> GenerationResult:
    """Extrait le brouillon + le verdict juge de la sortie brute de Claude.

    Le brouillon est entre les marqueurs ; le verdict via
    :func:`argos_ops.judge.parse_judge_json` (tolère le bloc ```json```). Le
    verdict canonique est dérivé via :func:`apply_thresholds` — jamais lu du LLM.

    Raise :class:`ValueError` si le draft ou le bloc juge est introuvable.
    """
    draft_match = re.search(
        re.escape(_DRAFT_OPEN) + r"(.*?)" + re.escape(_DRAFT_CLOSE),
        output_text,
        re.DOTALL,
    )
    if not draft_match:
        raise ValueError("Brouillon introuvable (marqueurs manquants)")
    draft = draft_match.group(1).strip()

    # Le bloc juge est après le brouillon (évite de capter un JSON dans le draft).
    after = output_text[draft_match.end() :]
    report = parse_judge_json(after)
    return GenerationResult(draft=draft, report=report, verdict=apply_thresholds(report))


# =============================================================================
# Gâchette (peut-on AGIR ?) — human-in-the-loop par défaut
# =============================================================================
def can_act(verdict: JudgeVerdict, *, human_approved: bool) -> bool:
    """Décide si l'action irréversible est autorisée.

    Règle (human-in-the-loop) :
    - ``killed`` → JAMAIS (même approuvé : le juge a bloqué pour conformité).
    - sinon → uniquement si l'humain a explicitement approuvé.

    NB : même ``auto_send`` exige le clic humain depuis le web — on n'agit
    jamais par surprise. L'auto-envoi sans humain reste réservé au pipeline
    cron/bot, pas à la console.
    """
    if verdict == "killed":
        return False
    return human_approved


def is_bot_live(name: str, settings: Settings) -> bool:
    """Vrai si AGIR déclencherait une action réelle (vs brouillon shadow).

    Conservateur : un bot inconnu de la table → SHADOW (``False``). Sert au badge
    SHADOW/LIVE de la console (« ne jamais agir en croyant être en dry-run »).
    """
    attr = _LIVE_FLAG_BY_BOT.get(name)
    return bool(getattr(settings, attr, False)) if attr else False


def read_live_status(name: str) -> bool:
    """Lit l'état LIVE/SHADOW À CHAUD pour le badge (affichage seul, Axe 4).

    Relit les Settings (.env / .env.local) via une instance fraîche à chaque
    appel : le badge reflète un flip de flag sans redémarrer le panel. La
    primitive testable reste :func:`is_bot_live` (Settings injectés) ; l'action
    réelle (``console_act``) rafraîchit le singleton avant d'agir.
    """
    return is_bot_live(name, Settings())


__all__ = [
    "GenerationResult",
    "InComposition",
    "InSource",
    "build_generate_prompt",
    "can_act",
    "compose_in",
    "is_bot_live",
    "parse_generation",
    "read_live_status",
]
