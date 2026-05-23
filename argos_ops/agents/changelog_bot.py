"""ChangelogBot — Product Marketing (P22.G Produit Sprint 11).

Génère un changelog Markdown depuis l'historique git entre deux refs.
Conventional commits regroupés (feat / fix / perf / refactor / docs /
test / chore / other). Écrit ``data/public/changelog_<period>.md``.

Lecture seule git — aucun side-effect repo. Idempotent : un fichier
existant n'est pas écrasé sans flag. Si pas de tags définis, prend les
100 derniers commits par défaut.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
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
from argos_ops.product.git_history import Commit, group_by_type, list_commits, list_tags

DEFAULT_CHANGELOG_DIR: Path = REPO_ROOT / "data" / "public"

# Titres lisibles par section, ordre fixe (≈ keepachangelog)
_SECTION_TITLES: dict[str, str] = {
    "feat": "✨ Nouveautés",
    "fix": "🐛 Corrections",
    "perf": "⚡ Performance",
    "refactor": "♻️ Refactoring",
    "docs": "📚 Documentation",
    "test": "✅ Tests",
    "chore": "🧹 Maintenance",
    "other": "📦 Autres",
}


@dataclass
class ChangelogResult:
    period: str
    commits_total: int = 0
    sections: dict[str, list[Commit]] = field(default_factory=dict)
    path: Path | None = None
    skipped_existing: bool = False

    def summary(self) -> str:
        if self.skipped_existing:
            return f"period={self.period} skipped (already exists)"
        return f"period={self.period} commits={self.commits_total} sections={len(self.sections)}"


def render_changelog(
    *,
    period_label: str,
    from_ref: str | None,
    to_ref: str,
    sections: dict[str, list[Commit]],
) -> str:
    """Rend le markdown du changelog (sans front-matter)."""
    parts = [f"# Changelog — {period_label}\n"]
    range_descr = (
        f"{from_ref} → {to_ref}"
        if from_ref is not None
        else f"100 derniers commits jusqu'à {to_ref}"
    )
    parts.append(f"> {range_descr}. Généré par ChangelogBot le {date.today().isoformat()}.\n")
    for key, title in _SECTION_TITLES.items():
        commits = sections.get(key, [])
        if not commits:
            continue
        parts.append(f"\n## {title}\n")
        for c in commits:
            scope = f"**{c.scope}** — " if c.scope else ""
            breaking = " 💥" if c.breaking else ""
            parts.append(f"- {scope}{c.description}{breaking} (`{c.sha}`)")
    return "\n".join(parts) + "\n"


def _period_label(from_ref: str | None, to_ref: str) -> str:
    if from_ref is None:
        return f"derniers commits → {to_ref}"
    return f"{from_ref} → {to_ref}"


def _period_slug(from_ref: str | None, to_ref: str) -> str:
    if from_ref is None:
        return f"recent-{date.today().isoformat()}"
    safe_from = from_ref.replace("/", "-")
    safe_to = to_ref.replace("/", "-")
    return f"{safe_from}--{safe_to}"


def build_changelog_embed(result: ChangelogResult) -> Embed:
    color = GREEN if result.skipped_existing else YELLOW
    fields = [
        EmbedField(name="Période", value=result.period, inline=True),
        EmbedField(name="Commits", value=str(result.commits_total), inline=True),
    ]
    if result.sections:
        lines = [f"• {_SECTION_TITLES[k]}: {len(v)}" for k, v in result.sections.items()]
        fields.append(EmbedField(name="Par type", value="\n".join(lines), inline=False))
    return Embed(
        title=f"ChangelogBot — {result.period}",
        description=(
            f"Changelog draft : `{result.path}`. Peaufiner avant publication."
            if result.path and not result.skipped_existing
            else "Changelog déjà existant — relancer avec un autre range pour regénérer."
        ),
        color=color,
        fields=fields,
        footer="Argos Ops • ChangelogBot",
    )


class ChangelogBot(BaseAgent):
    """Génère un changelog Markdown depuis ``git log`` entre deux refs."""

    name = "ChangelogBot"
    command = "/draft-changelog"
    breaker_name = "ChangelogBot"

    def __init__(
        self,
        *,
        from_ref: str | None = None,
        to_ref: str = "HEAD",
        output_dir: Path = DEFAULT_CHANGELOG_DIR,
        force: bool = False,
    ) -> None:
        self._from_ref = from_ref
        self._to_ref = to_ref
        self._output_dir = output_dir
        self._force = force

    async def run(self) -> RunResult:
        settings = get_settings()
        from_ref = self._from_ref
        if from_ref is None:
            tags = list_tags()
            from_ref = tags[0] if tags else None  # le tag le plus récent comme base

        try:
            commits = list_commits(from_ref=from_ref, to_ref=self._to_ref)
        except Exception as exc:
            logger.exception(f"ChangelogBot — git log échoué : {exc}")
            return RunResult(
                status="failed",
                output_summary=None,
                error=f"git log failed: {exc}",
            )

        period_label = _period_label(from_ref, self._to_ref)
        result = ChangelogResult(period=period_label, commits_total=len(commits))

        if not commits:
            logger.info(f"ChangelogBot — aucun commit ({period_label})")
            return RunResult(status="success", output_summary=f"silence (no commits {period_label})")

        sections = group_by_type(commits)
        result.sections = sections

        self._output_dir.mkdir(parents=True, exist_ok=True)
        slug = _period_slug(from_ref, self._to_ref)
        path = self._output_dir / f"changelog_{slug}.md"
        if path.exists() and not self._force:
            result.skipped_existing = True
            result.path = path
            logger.info(f"ChangelogBot — déjà existant : {path}")
            return RunResult(status="success", output_summary=result.summary())

        path.write_text(
            render_changelog(
                period_label=period_label,
                from_ref=from_ref,
                to_ref=self._to_ref,
                sections=sections,
            ),
            encoding="utf-8",
        )
        result.path = path

        webhook = settings.discord_webhook_ops_logs or settings.discord_webhook_alerts
        if webhook is not None:
            try:
                await send_embed(webhook, build_changelog_embed(result))
            except Exception as exc:
                logger.warning(f"ChangelogBot — notif Discord échouée : {exc}")

        return RunResult(status="success", output_summary=result.summary(), extras={"path": str(path)})


__all__ = [
    "DEFAULT_CHANGELOG_DIR",
    "ChangelogBot",
    "ChangelogResult",
    "build_changelog_embed",
    "render_changelog",
]
