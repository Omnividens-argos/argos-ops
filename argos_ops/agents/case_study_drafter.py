"""CaseStudyDrafter — drafte le squelette d'une case study client référence.

Lit ``data/crm/case_study_candidates.yaml`` (alimenté manuellement après
validation founder) et pour chaque candidat ``status: ready``, écrit un
squelette MD dans ``data/marketing/case_studies/<slug>.md`` avec :

- frontmatter status: drafted, customer, sector, validated_by
- sections canoniques (contexte, problème, solution Argos, résultats
  chiffrés, verbatim, next steps)

Pas de scraping Stripe ici : les chiffres MRR / nb scans viennent du
candidat YAML, le founder a déjà validé qu'on peut les publier.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml
from loguru import logger

from argos_ops.agents.base import BaseAgent, RunResult
from argos_ops.config import REPO_ROOT, get_settings
from argos_ops.notifications.discord import GREEN, YELLOW, Embed, EmbedField, send_embed

CANDIDATES_PATH = REPO_ROOT / "data" / "crm" / "case_study_candidates.yaml"
STUDIES_DIR = REPO_ROOT / "data" / "marketing" / "case_studies"


@dataclass
class CaseStudyCandidate:
    slug: str
    customer: str
    sector: str
    context: str
    problem: str
    solution: str
    results: list[str] = field(default_factory=list)
    quote: str = ""
    status: str = "ready"


@dataclass
class DrafterStats:
    candidates: int = 0
    drafted: int = 0
    skipped_existing: int = 0
    skipped_not_ready: int = 0

    def summary(self) -> str:
        return (
            f"candidates={self.candidates} drafted={self.drafted} "
            f"existing={self.skipped_existing} not_ready={self.skipped_not_ready}"
        )


def load_candidates(path: Path | None = None) -> list[CaseStudyCandidate]:
    path = path or CANDIDATES_PATH
    if not path.exists():
        return []
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    out: list[CaseStudyCandidate] = []
    for entry in raw.get("candidates", []):
        if not isinstance(entry, dict):
            continue
        try:
            out.append(
                CaseStudyCandidate(
                    slug=str(entry["slug"]),
                    customer=str(entry["customer"]),
                    sector=str(entry.get("sector", "")),
                    context=str(entry.get("context", "")),
                    problem=str(entry.get("problem", "")),
                    solution=str(entry.get("solution", "")),
                    results=[str(r) for r in entry.get("results", []) if r],
                    quote=str(entry.get("quote", "")),
                    status=str(entry.get("status", "ready")),
                )
            )
        except KeyError:
            continue
    return out


def draft_case_study(c: CaseStudyCandidate) -> str:
    results_lines = "\n".join(f"- {r}" for r in c.results) if c.results else "- (à compléter)"
    quote_section = (
        f"\n## Verbatim\n\n> « {c.quote} »\n\n— {c.customer}\n" if c.quote else "\n## Verbatim\n\n_À solliciter via TestimonialHunter._\n"
    )
    return (
        f"---\nstatus: drafted\ncustomer: {c.customer}\nsector: {c.sector}\n"
        f"slug: {c.slug}\nvalidated_by: founder\n---\n\n"
        f"# Cas client {c.customer}\n\n"
        f"## Contexte\n\n{c.context}\n\n"
        f"## Problème\n\n{c.problem}\n\n"
        f"## Solution Argos\n\n{c.solution}\n\n"
        f"## Résultats\n\n{results_lines}\n"
        f"{quote_section}\n"
        f"## Next steps\n\n"
        f"- Validation finale par le client avant publication\n"
        f"- Publication sur omnividens.fr/clients/{c.slug}\n"
        f"- Reposter version courte (LinkedIn carousel) via ContentBot\n"
    )


def build_drafter_embed(stats: DrafterStats) -> Embed:
    color = GREEN if stats.drafted > 0 or stats.candidates == 0 else YELLOW
    return Embed(
        title=f"Argos — CaseStudyDrafter ({stats.drafted} nouvelles)",
        color=color,
        fields=[
            EmbedField(name="Candidats", value=str(stats.candidates), inline=True),
            EmbedField(name="Draftés", value=str(stats.drafted), inline=True),
            EmbedField(name="Déjà draftés", value=str(stats.skipped_existing), inline=True),
        ],
        footer="Argos Ops • CaseStudyDrafter",
    )


class CaseStudyDrafter(BaseAgent):
    """Drafte le squelette d'une case study client référence."""

    name = "CaseStudyDrafter"
    command = "/draft-case-study"
    breaker_name = "CaseStudyDrafter"

    async def run(self) -> RunResult:
        candidates = load_candidates()
        stats = DrafterStats(candidates=len(candidates))
        STUDIES_DIR.mkdir(parents=True, exist_ok=True)

        for c in candidates:
            if c.status != "ready":
                stats.skipped_not_ready += 1
                continue
            path = STUDIES_DIR / f"{c.slug}.md"
            if path.exists():
                stats.skipped_existing += 1
                continue
            try:
                path.write_text(draft_case_study(c), encoding="utf-8")
                stats.drafted += 1
            except OSError as exc:
                logger.warning(f"CaseStudyDrafter — écriture {c.slug} : {exc}")

        settings = get_settings()
        webhook = settings.discord_webhook_content or settings.discord_webhook_ops_logs
        if webhook is not None and stats.drafted > 0:
            try:
                await send_embed(webhook, build_drafter_embed(stats))
            except Exception as exc:
                logger.warning(f"CaseStudyDrafter — notif Discord : {exc}")

        return RunResult(status="success", output_summary=stats.summary())


__all__ = [
    "CANDIDATES_PATH",
    "STUDIES_DIR",
    "CaseStudyCandidate",
    "CaseStudyDrafter",
    "DrafterStats",
    "build_drafter_embed",
    "draft_case_study",
    "load_candidates",
]
