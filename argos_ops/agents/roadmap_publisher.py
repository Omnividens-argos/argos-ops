"""RoadmapPublisher — Head of Product (P22.G Produit Sprint 11).

Lit l'Annexe D de ``docs/ARGOS_OPS_PLAN.md`` (source unique d'avancement)
et publie une roadmap publique épurée dans ``data/public/roadmap.md`` :
- groupée par service (12 catégories)
- 3 sections : Livré / En cours / À venir
- **sans codes sprint internes** (P22.X retirés du status)
- description et rôle nettoyés (pas de liens Markdown internes)

Idempotent — la roadmap publique est entièrement réécrite à chaque run
pour refléter l'Annexe D courante.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from loguru import logger

from argos_ops.agents.base import BaseAgent, RunResult
from argos_ops.config import REPO_ROOT, get_settings
from argos_ops.notifications.discord import (
    GREEN,
    YELLOW,
    Embed,
    EmbedField,
    send_embed,
)
from argos_ops.product.annexe_d_parser import BotEntry, count_states, parse_annexe_d

DEFAULT_ANNEXE_PATH: Path = REPO_ROOT / "docs" / "ARGOS_OPS_PLAN.md"
DEFAULT_OUTPUT_PATH: Path = REPO_ROOT / "data" / "public" / "roadmap.md"

# Regex pour virer les codes sprint internes : P22.C, P13.B, Sprint 7, etc.
_SPRINT_CODE_RE = re.compile(
    r"\b(?:P\d+(?:\.[A-Za-z])?|Sprint\s+\d+\+?)\b",
    flags=re.IGNORECASE,
)


@dataclass
class RoadmapStats:
    entries_total: int = 0
    done: int = 0
    partial: int = 0
    roadmap: int = 0
    services: int = 0
    output_path: Path | None = None

    def summary(self) -> str:
        return (
            f"entries={self.entries_total} done={self.done} partial={self.partial} "
            f"roadmap={self.roadmap} services={self.services}"
        )


def _public_status(entry: BotEntry) -> str:
    """Transforme le ``status_note`` interne en libellé public.

    Exemples :
    - "P7 livré 2026-05-09" → "livré"
    - "P22.C livré 2026-05-23." → "livré (mai 2026)"
    - "Sprint 12." → "" (futur, pas de date)
    """
    note = entry.status_note or ""
    # Date YYYY-MM-DD → "mois année"
    date_match = re.search(r"(\d{4})-(\d{2})-\d{2}", note)
    if date_match and entry.state in ("done", "partial"):
        year, month = date_match.group(1), int(date_match.group(2))
        months = (
            "janvier", "février", "mars", "avril", "mai", "juin",
            "juillet", "août", "septembre", "octobre", "novembre", "décembre",
        )
        if 1 <= month <= 12:
            return f"livré ({months[month - 1]} {year})" if entry.state == "done" else f"partiel ({months[month - 1]} {year})"
    if entry.state == "done":
        return "livré"
    if entry.state == "partial":
        return "partiel"
    return ""  # roadmap = pas de date publique


def render_public_roadmap(entries: list[BotEntry]) -> str:
    """Rend le markdown roadmap publique groupé par service + état."""
    today_year = "2026"
    parts = [
        "# Roadmap publique Argos / Omnividens\n",
        "> État de la flotte d'agents Argos Ops, mis à jour automatiquement\n"
        "> depuis l'Annexe D interne. Les codes sprint internes sont retirés.\n",
    ]

    counts = count_states(entries)
    total = sum(counts.values())
    if total > 0:
        parts.append(
            f"\n**État global** — {counts['done']} livrés, {counts['partial']} partiels, "
            f"{counts['roadmap']} à venir / {total} bots cibles.\n"
        )

    by_service: dict[str, list[BotEntry]] = {}
    for entry in entries:
        by_service.setdefault(entry.service, []).append(entry)

    for service, group in by_service.items():
        parts.append(f"\n## {service}\n")
        done = [e for e in group if e.state == "done"]
        partial = [e for e in group if e.state == "partial"]
        upcoming = [e for e in group if e.state == "roadmap"]
        if done:
            parts.append("\n**Livré**")
            for e in done:
                public_note = _public_status(e)
                desc_clean = _SPRINT_CODE_RE.sub("", e.description).strip()
                note_part = f" — _{public_note}_" if public_note else ""
                parts.append(f"- **{e.name}** — {desc_clean}{note_part}")
        if partial:
            parts.append("\n**En cours**")
            for e in partial:
                public_note = _public_status(e)
                desc_clean = _SPRINT_CODE_RE.sub("", e.description).strip()
                note_part = f" — _{public_note}_" if public_note else ""
                parts.append(f"- **{e.name}** — {desc_clean}{note_part}")
        if upcoming:
            parts.append("\n**À venir**")
            for e in upcoming:
                desc_clean = _SPRINT_CODE_RE.sub("", e.description).strip()
                parts.append(f"- **{e.name}** — {desc_clean}")

    parts.append(f"\n---\n\nDernière mise à jour : roadmap auto-générée depuis l'Annexe D ({today_year}).\n")
    return "\n".join(parts) + "\n"


def build_roadmap_embed(stats: RoadmapStats) -> Embed:
    color = YELLOW if stats.entries_total > 0 else GREEN
    fields = [
        EmbedField(name="Entrées", value=str(stats.entries_total), inline=True),
        EmbedField(name="Livrés", value=str(stats.done), inline=True),
        EmbedField(name="Partiels", value=str(stats.partial), inline=True),
        EmbedField(name="À venir", value=str(stats.roadmap), inline=True),
        EmbedField(name="Services", value=str(stats.services), inline=True),
    ]
    return Embed(
        title="RoadmapPublisher — roadmap publique régénérée",
        description=(
            f"Output : `{stats.output_path}`. Revue founder avant push site."
            if stats.output_path
            else "Annexe D vide — rien à publier."
        ),
        color=color,
        fields=fields,
        footer="Argos Ops • RoadmapPublisher",
    )


class RoadmapPublisher(BaseAgent):
    """Génère la roadmap publique depuis l'Annexe D interne."""

    name = "RoadmapPublisher"
    command = "/publish-roadmap"
    breaker_name = "RoadmapPublisher"
    ai_act_risk_class = "minimal"

    def __init__(
        self,
        *,
        annexe_path: Path = DEFAULT_ANNEXE_PATH,
        output_path: Path = DEFAULT_OUTPUT_PATH,
    ) -> None:
        self._annexe_path = annexe_path
        self._output_path = output_path

    async def run(self) -> RunResult:
        settings = get_settings()
        entries = parse_annexe_d(self._annexe_path)
        if not entries:
            logger.info(f"RoadmapPublisher — Annexe D vide ({self._annexe_path})")
            return RunResult(status="success", output_summary="silence (no entries)")

        counts = count_states(entries)
        services = {e.service for e in entries}
        stats = RoadmapStats(
            entries_total=len(entries),
            done=counts["done"],
            partial=counts["partial"],
            roadmap=counts["roadmap"],
            services=len(services),
        )

        self._output_path.parent.mkdir(parents=True, exist_ok=True)
        self._output_path.write_text(render_public_roadmap(entries), encoding="utf-8")
        stats.output_path = self._output_path

        webhook = settings.discord_webhook_ops_logs or settings.discord_webhook_alerts
        if webhook is not None:
            try:
                await send_embed(webhook, build_roadmap_embed(stats))
            except Exception as exc:
                logger.warning(f"RoadmapPublisher — notif Discord échouée : {exc}")

        return RunResult(status="success", output_summary=stats.summary())


__all__ = [
    "DEFAULT_ANNEXE_PATH",
    "DEFAULT_OUTPUT_PATH",
    "RoadmapPublisher",
    "RoadmapStats",
    "build_roadmap_embed",
    "render_public_roadmap",
]
