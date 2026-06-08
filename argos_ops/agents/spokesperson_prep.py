"""SpokespersonPrep — Q&A briefs pour interviews founder.

À partir de ``data/comm/interviews/upcoming.yaml`` (interviews à venir
dans les 7 jours), drafte une fiche Q&A canonique dans
``data/comm/interviews/<slug>/qa_brief.md`` :

- 5 questions probables (selon outlet + beat)
- Réponses suggérées en bullet points (à raffiner par le founder)
- Stats clés Argos à avoir en tête (chiffres MRR / pentest livrés /
  CVE découvertes — lus depuis ``data/comm/founder_stats.yaml``)
- Liste de no-go topics

Aucun envoi — humain-in-the-loop strict.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import yaml
from loguru import logger

from argos_ops.agents.base import BaseAgent, IOItem, RunResult
from argos_ops.config import REPO_ROOT, get_settings
from argos_ops.notifications.discord import GREEN, YELLOW, Embed, EmbedField, send_embed

INTERVIEWS_PATH = REPO_ROOT / "data" / "comm" / "interviews" / "upcoming.yaml"
INTERVIEWS_DIR = REPO_ROOT / "data" / "comm" / "interviews"
STATS_PATH = REPO_ROOT / "data" / "comm" / "founder_stats.yaml"


QUESTION_BANK: dict[str, list[str]] = {
    "cyber": [
        "Quelle est la principale faille que vous voyez chez les PME aujourd'hui ?",
        "Comment Argos se positionne face aux scanners type Nessus ?",
        "Quel a été votre finding le plus impactant pour un client ?",
        "Comment gérez-vous les faux positifs ?",
        "Quel est votre point de vue sur l'AI Act pour les outils cyber ?",
    ],
    "business": [
        "Pourquoi avoir choisi de cibler les PME plutôt que les grands comptes ?",
        "Quel est votre modèle économique ?",
        "Quels sont vos objectifs MRR à 12 mois ?",
        "Comment se positionnent Argos / Omnividens face aux acteurs établis ?",
        "Avez-vous des plans de levée de fonds ?",
    ],
    "startup": [
        "Qu'est-ce qui vous a décidé à monter Omnividens ?",
        "Quelle est votre équipe aujourd'hui ?",
        "Quels conseils pour un founder solo en cybersécurité ?",
        "Quelles sont vos métriques d'activation ?",
        "Quels sont les défis du SaaS BtoB en cyber ?",
    ],
}

NO_GO_TOPICS = [
    "Détails techniques des findings clients (NDA strict)",
    "Identité des clients sauf mention publique pré-validée",
    "Chiffres précis revenus si non publiés (préférer ordres de grandeur)",
    "Spéculations sur acteurs concurrents (commenter le marché, pas les noms)",
]


@dataclass
class Interview:
    slug: str
    outlet: str
    journalist: str
    date: date
    beat: str = "cyber"
    duration_minutes: int = 30


@dataclass
class PrepStats:
    upcoming: int = 0
    briefed: int = 0
    skipped_existing: int = 0
    interviews: list[str] = field(default_factory=list)

    def summary(self) -> str:
        return (
            f"upcoming={self.upcoming} briefed={self.briefed} "
            f"existing={self.skipped_existing}"
        )


def load_upcoming(path: Path | None = None) -> list[Interview]:
    path = path or INTERVIEWS_PATH
    if not path.exists():
        return []
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    out: list[Interview] = []
    for entry in raw.get("interviews", []):
        if not isinstance(entry, dict):
            continue
        d = entry.get("date")
        if isinstance(d, str):
            try:
                d_date = date.fromisoformat(d)
            except ValueError:
                continue
        elif isinstance(d, date):
            d_date = d
        else:
            continue
        try:
            out.append(
                Interview(
                    slug=str(entry["slug"]),
                    outlet=str(entry["outlet"]),
                    journalist=str(entry["journalist"]),
                    date=d_date,
                    beat=str(entry.get("beat", "cyber")),
                    duration_minutes=int(entry.get("duration_minutes", 30)),
                )
            )
        except (KeyError, ValueError):
            continue
    return out


def load_founder_stats(path: Path | None = None) -> dict[str, object]:
    path = path or STATS_PATH
    if not path.exists():
        return {}
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return raw if isinstance(raw, dict) else {}


def draft_qa_brief(interview: Interview, founder_stats: dict[str, object]) -> str:
    questions = QUESTION_BANK.get(interview.beat, QUESTION_BANK["cyber"])
    stats_lines = (
        "\n".join(f"- {k} : **{v}**" for k, v in founder_stats.items())
        if founder_stats
        else "_(à compléter dans data/comm/founder_stats.yaml)_"
    )
    qa_block = "\n\n".join(
        f"### Q{i + 1} — {q}\n\n- (à raffiner) Élément factuel\n- (à raffiner) Anecdote terrain\n- (à raffiner) Pivot vers Argos"
        for i, q in enumerate(questions)
    )
    no_go = "\n".join(f"- {t}" for t in NO_GO_TOPICS)
    return (
        f"---\nstatus: drafted\nslug: {interview.slug}\noutlet: {interview.outlet}\n"
        f"journalist: {interview.journalist}\ndate: {interview.date.isoformat()}\n"
        f"beat: {interview.beat}\n---\n\n"
        f"# Brief Q&A — {interview.outlet}\n\n"
        f"**Journaliste** : {interview.journalist} · "
        f"**Durée** : {interview.duration_minutes} min · "
        f"**Date** : {interview.date.isoformat()}\n\n"
        f"## Stats clés à avoir en tête\n\n{stats_lines}\n\n"
        f"## Questions probables\n\n{qa_block}\n\n"
        f"## No-go topics\n\n{no_go}\n\n"
        f"## Post-interview\n\n"
        f"- [ ] Demander le bon à tirer si quotes attribuées\n"
        f"- [ ] Demander date de publication estimée\n"
        f"- [ ] Ajouter au tracker `data/comm/press_mentions.yaml` une fois sorti\n"
    )


def build_prep_embed(stats: PrepStats) -> Embed:
    color = GREEN if stats.briefed > 0 or stats.upcoming == 0 else YELLOW
    fields = [
        EmbedField(name="À venir 7j", value=str(stats.upcoming), inline=True),
        EmbedField(name="Briefés", value=str(stats.briefed), inline=True),
        EmbedField(name="Déjà briefés", value=str(stats.skipped_existing), inline=True),
    ]
    if stats.interviews:
        fields.append(
            EmbedField(
                name="Interviews",
                value="\n".join(f"• {i}" for i in stats.interviews[:5]),
                inline=False,
            )
        )
    return Embed(
        title="Argos — SpokespersonPrep",
        color=color,
        fields=fields,
        footer="Argos Ops • SpokespersonPrep",
    )


class SpokespersonPrep(BaseAgent):
    """Drafte un Q&A brief pour chaque interview dans la semaine."""

    name = "SpokespersonPrep"
    command = "/prep-interview"
    breaker_name = "SpokespersonPrep"
    ai_act_risk_class = "limited"

    async def run(self) -> RunResult:
        today = datetime.now(UTC).date()
        interviews = load_upcoming()
        upcoming = [i for i in interviews if today <= i.date <= today + timedelta(days=7)]
        stats = PrepStats(upcoming=len(upcoming))
        founder_stats = load_founder_stats()

        for interview in upcoming:
            base = INTERVIEWS_DIR / interview.slug
            base.mkdir(parents=True, exist_ok=True)
            path = base / "qa_brief.md"
            if path.exists():
                stats.skipped_existing += 1
                continue
            try:
                path.write_text(draft_qa_brief(interview, founder_stats), encoding="utf-8")
                stats.briefed += 1
                stats.interviews.append(interview.slug)
            except OSError as exc:
                logger.warning(f"SpokespersonPrep — écriture {interview.slug} : {exc}")

        settings = get_settings()
        webhook = settings.discord_webhook_alerts or settings.discord_webhook_ops_logs
        if webhook is not None and stats.upcoming > 0:
            try:
                await send_embed(webhook, build_prep_embed(stats))
            except Exception as exc:
                logger.warning(f"SpokespersonPrep — notif Discord : {exc}")

        inputs = [
            IOItem(
                label="Interviews à venir (7j)",
                kind="file",
                detail="upcoming.yaml filtré sur la fenêtre 7j",
                ref="data/comm/interviews/upcoming.yaml",
                count=stats.upcoming,
            ),
            IOItem(
                label="Stats clés fondateur",
                kind="file",
                detail="chiffres à avoir en tête en interview",
                ref="data/comm/founder_stats.yaml",
            ),
        ]
        outputs: list[IOItem] = []
        if stats.briefed:
            outputs.append(
                IOItem(
                    label="Briefs Q&A draftés",
                    kind="draft",
                    detail=(
                        "data/comm/interviews/<slug>/qa_brief.md · "
                        + ", ".join(stats.interviews[:5])
                    ),
                    count=stats.briefed,
                )
            )
        if stats.skipped_existing:
            outputs.append(
                IOItem(
                    label="Briefs déjà existants (ignorés)",
                    kind="draft",
                    count=stats.skipped_existing,
                )
            )
        return RunResult(
            status="success",
            output_summary=stats.summary(),
            inputs=inputs,
            outputs=outputs,
        )


__all__ = [
    "INTERVIEWS_DIR",
    "INTERVIEWS_PATH",
    "NO_GO_TOPICS",
    "QUESTION_BANK",
    "STATS_PATH",
    "Interview",
    "PrepStats",
    "SpokespersonPrep",
    "build_prep_embed",
    "draft_qa_brief",
    "load_founder_stats",
    "load_upcoming",
]
