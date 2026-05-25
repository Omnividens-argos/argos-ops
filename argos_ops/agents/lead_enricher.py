"""LeadEnricher — Lead Intel commercial (P22.H Sales Sprint 3).

Porte le skill markdown ``.claude/skills/lead-enricher/`` en agent
Python autonome — batch sur tout l'inbox CSV plutôt qu'un seul lead à
la fois. Le skill reste exécuté en humain-in-the-loop par
``/draft-outbound`` quand on veut affiner ; LeadEnricher (agent) pré-
traite l'inbox quotidiennement pour ne pas refaire le travail à la
main.

Source ``data/outbound/inbox/leads.csv`` (alimenté par ProspectMiner
ou import manuel). Output ``data/outbound/enriched/<slug>.md`` :
frontmatter YAML + body lisible. Idempotent — si l'enriched existe
déjà, on ne le réécrit pas (le fondateur peut avoir affiné à la main).

Aucun appel LLM (D-017) — uniquement les heuristiques de
:mod:`argos_ops.sales.enrichment` (BANT + persona + email guess).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from loguru import logger

from argos_ops.agents.base import BaseAgent, RunResult
from argos_ops.config import get_settings
from argos_ops.exceptions import AgentDataSourceError
from argos_ops.notifications.discord import (
    GREEN,
    YELLOW,
    Embed,
    EmbedField,
    send_embed,
)
from argos_ops.outbound.sequence import ENRICHED_DIR, INBOX_DIR, read_inbox_csv
from argos_ops.outbound.templates import slugify
from argos_ops.sales.enrichment import enrich_lead


@dataclass
class EnrichmentStats:
    """Compteurs d'un run."""

    leads_seen: int = 0
    newly_enriched: int = 0
    already_enriched: int = 0
    qualified: int = 0  # BANT total >= 40
    skipped_invalid: int = 0
    new_slugs: list[str] = field(default_factory=list)

    def summary(self) -> str:
        return (
            f"seen={self.leads_seen} new={self.newly_enriched} "
            f"already={self.already_enriched} qualified={self.qualified} "
            f"invalid={self.skipped_invalid}"
        )


def _write_enriched_md(
    out_path: Path,
    *,
    full_name: str,
    domain: str,
    enriched: dict[str, Any],
) -> None:
    """Écrit le fichier ``<slug>.md`` avec frontmatter YAML + body Markdown."""
    bant = enriched["bant"]
    persona = enriched["persona"]
    out_path.parent.mkdir(parents=True, exist_ok=True)
    front = yaml.safe_dump(
        {
            "full_name": full_name,
            "domain": domain,
            "title_hint": enriched.get("title_hint"),
            "email_guesses": enriched["email_guesses"],
            "persona": persona,
            "bant": bant,
            "enriched_by": "LeadEnricher",
            "status": "enriched",
        },
        allow_unicode=True,
        sort_keys=False,
    )
    bant_block = (
        f"- **Budget** : {bant['budget']}/30  \n"
        f"- **Authority** : {bant['authority']}/25  \n"
        f"- **Need** : {bant['need']}/25  \n"
        f"- **Timing** : {bant['timing']}/20  \n"
        f"- **Total** : **{bant['total']}/100** "
        f"({'qualified' if bant['is_qualified'] else 'sous le seuil'})\n"
    )
    persona_block = (
        f"- **Persona ICP** : {persona['name']} ({persona['score']}/100)  \n"
        f"- **Mots-clés matchés** : {', '.join(persona['matched_keywords']) or '—'}\n"
    )
    email_lines = "\n".join(
        f"- `{g['email']}` — pattern *{g['pattern']}*, confidence {g['confidence']}"
        for g in enriched["email_guesses"]
    )
    body = (
        f"---\n{front}---\n\n"
        f"# {full_name} — {domain}\n\n"
        f"## BANT\n\n{bant_block}\n"
        f"## Persona\n\n{persona_block}\n"
        f"## Candidats email\n\n{email_lines or '_(nom non parseable)_'}\n\n"
        f"## Notes\n\n"
        f"_Section libre pour le fondateur — signaux ICP, conversations "
        f"passées, etc. LeadEnricher ne touche jamais à ce bloc._\n"
    )
    out_path.write_text(body, encoding="utf-8")


def build_enrichment_embed(stats: EnrichmentStats) -> Embed:
    """Embed Discord récap."""
    color = YELLOW if stats.newly_enriched > 0 else GREEN
    fields = [
        EmbedField(name="Lus", value=str(stats.leads_seen), inline=True),
        EmbedField(name="Nouvellement enrichis", value=str(stats.newly_enriched), inline=True),
        EmbedField(name="Déjà enrichis", value=str(stats.already_enriched), inline=True),
        EmbedField(name="Qualifiés (BANT ≥ 40)", value=str(stats.qualified), inline=True),
        EmbedField(name="Invalides", value=str(stats.skipped_invalid), inline=True),
    ]
    if stats.new_slugs:
        preview = [f"• {s}" for s in stats.new_slugs[:5]]
        if len(stats.new_slugs) > 5:
            preview.append(f"... +{len(stats.new_slugs) - 5} autres")
        fields.append(EmbedField(name="Slugs créés", value="\n".join(preview), inline=False))
    return Embed(
        title=f"LeadEnricher — {stats.newly_enriched} fiches enrichies",
        description=(
            "Inspecte `data/outbound/enriched/` puis lance `/run-outbound-bot` "
            "pour scaffold les séquences."
            if stats.newly_enriched > 0
            else "Inbox sans nouveau lead à enrichir."
        ),
        color=color,
        fields=fields,
        footer="Argos Ops • LeadEnricher",
    )


class LeadEnricher(BaseAgent):
    """Enrichit chaque lead inbox en fiche Markdown (BANT / persona / emails)."""

    name = "LeadEnricher"
    command = "/run-lead-enrich"
    breaker_name = "LeadEnricher"
    ai_act_risk_class = "minimal"

    def __init__(
        self,
        *,
        inbox_dir: Path = INBOX_DIR,
        enriched_dir: Path = ENRICHED_DIR,
    ) -> None:
        self._inbox_dir = inbox_dir
        self._enriched_dir = enriched_dir

    async def run(self) -> RunResult:
        settings = get_settings()
        csv_path = self._inbox_dir / "leads.csv"
        if not csv_path.exists():
            logger.info(f"LeadEnricher — aucun CSV à enrichir ({csv_path})")
            return RunResult(status="success", output_summary="silence (no csv)")

        try:
            leads = read_inbox_csv(csv_path)
        except ValueError as exc:
            raise AgentDataSourceError(f"CSV invalide {csv_path.name}: {exc}") from exc

        stats = EnrichmentStats(leads_seen=len(leads))
        for lead in leads:
            slug = slugify(lead.full_name, lead.domain)
            out_path = self._enriched_dir / f"{slug}.md"
            if out_path.exists():
                stats.already_enriched += 1
                continue
            enriched = enrich_lead(
                full_name=lead.full_name,
                domain=lead.domain,
                title_hint=lead.title_hint,
            )
            bant = enriched["bant"]
            assert isinstance(bant, dict)
            if bant["is_qualified"]:
                stats.qualified += 1
            try:
                _write_enriched_md(
                    out_path,
                    full_name=lead.full_name,
                    domain=lead.domain,
                    enriched=enriched,
                )
                stats.newly_enriched += 1
                stats.new_slugs.append(slug)
            except OSError as exc:
                logger.exception(f"LeadEnricher — écriture {slug} a échoué : {exc}")
                stats.skipped_invalid += 1

        webhook = settings.discord_webhook_ops_logs or settings.discord_webhook_alerts
        if webhook is not None:
            try:
                await send_embed(webhook, build_enrichment_embed(stats))
            except Exception as exc:
                logger.warning(f"LeadEnricher — notif Discord a échoué : {exc}")

        return RunResult(status="success", output_summary=stats.summary())


__all__ = ["EnrichmentStats", "LeadEnricher", "build_enrichment_embed"]
