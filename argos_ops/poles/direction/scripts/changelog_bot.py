"""``ChangelogBotScript`` — changelog depuis le snapshot de commits (Direction, S6).

Bras déterministe : lit le snapshot de commits
(:func:`argos_ops.poles.direction.changelog.build_changelog`) et écrit un fait
``kind="changelog"`` (artefact **public** — sa publication est soumise au garde-fou
release au niveau agent / API). Skip silencieux si aucun commit. Local-first.
"""

from __future__ import annotations

from argos_ops.poles.base import BaseScript, ScriptResult
from argos_ops.poles.direction import changelog


class ChangelogBotScript(BaseScript):
    """Changelog prêt à publier (``kind="changelog"``)."""

    pole = "direction"
    name = "changelog_bot"

    async def run(self) -> ScriptResult:
        view = changelog.build_changelog(poles_root=self.poles_root)
        if not view.n_commits:
            return ScriptResult(status="success", summary="aucun commit — skip", written=[])
        record = await self.write_memory(
            f"Changelog {view.period_label} : {view.n_commits} commit(s), "
            f"{view.n_sections} section(s) — prêt à publier.",
            kind="changelog",
            tags=("publish", "changelog"),
        )
        return ScriptResult(
            status="success", summary=f"{view.n_commits} commit(s)", written=[record]
        )


__all__ = ["ChangelogBotScript"]
