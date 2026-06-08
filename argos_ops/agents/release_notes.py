"""ReleaseNotesBot — Product Manager (P22.G Produit Sprint 11).

Drafte des release notes user-friendly par version, depuis un spec
``data/release_notes/spec.yaml`` rédigé par le founder ::

    releases:
      - version: "v0.7"
        date: "2026-05-23"
        highlights:
          - "Le scanner détecte 3 nouvelles classes de vulnérabilités."
          - "L'export PDF inclut un résumé exécutif (page 1)."
        improvements:
          - "Temps de scan moyen divisé par 2 sur les domaines > 50 pages."
        fixes:
          - "Les rapports ne plantaient plus en cas de SSL invalide."
        breaking_changes: []
        status: pending

Le bot transforme chaque release ``status: pending`` en
``data/public/release_notes/<version>.md`` avec frontmatter + ton
user-friendly (anti-jargon, anti-changelog brut).

Humain peaufine et lance ensuite (futur) un `/publish-release-notes`.
Le bot patch ``status: drafted`` après création. Idempotent.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any

import yaml
from loguru import logger

from argos_ops.agents.base import BaseAgent, IOItem, RunResult
from argos_ops.config import REPO_ROOT, get_settings
from argos_ops.notifications.discord import (
    GREEN,
    YELLOW,
    Embed,
    EmbedField,
    send_embed,
)

DEFAULT_SPEC_PATH: Path = REPO_ROOT / "data" / "release_notes" / "spec.yaml"
DEFAULT_OUTPUT_DIR: Path = REPO_ROOT / "data" / "public" / "release_notes"


@dataclass
class ReleaseNotesStats:
    releases_seen: int = 0
    drafted: int = 0
    already_done: int = 0
    drafts: list[str] = field(default_factory=list)

    def summary(self) -> str:
        return (
            f"releases={self.releases_seen} drafted={self.drafted} "
            f"already_done={self.already_done}"
        )


def _load_spec(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    releases = raw.get("releases", [])
    if not isinstance(releases, list):
        raise ValueError(f"release_notes/spec.yaml malformé : {path}")
    return releases


def _persist_spec(path: Path, releases: list[dict[str, Any]]) -> None:
    payload = {
        "updated_at": datetime.now().isoformat(),
        "releases": releases,
    }
    path.write_text(yaml.safe_dump(payload, allow_unicode=True, sort_keys=False), encoding="utf-8")


def render_release_notes(entry: dict[str, Any]) -> str:
    """Rend les release notes Markdown avec ton user-friendly."""
    version = entry["version"]
    when = entry.get("date", date.today().isoformat())
    highlights = entry.get("highlights", []) or []
    improvements = entry.get("improvements", []) or []
    fixes = entry.get("fixes", []) or []
    breaking = entry.get("breaking_changes", []) or []

    parts = [f"# Argos {version} — {when}\n"]
    parts.append(
        "> Notes de version pour les utilisateurs Argos. Pour le détail technique "
        "commit-par-commit, voir le changelog interne.\n"
    )

    if highlights:
        parts.append("\n## ✨ Ce qui change pour vous\n")
        for h in highlights:
            parts.append(f"- {h}")

    if improvements:
        parts.append("\n## ⚡ Améliorations\n")
        for i in improvements:
            parts.append(f"- {i}")

    if fixes:
        parts.append("\n## 🐛 Corrections\n")
        for f in fixes:
            parts.append(f"- {f}")

    if breaking:
        parts.append("\n## 💥 Changements incompatibles\n")
        parts.append("> Action requise de votre côté avant la prochaine montée de version.\n")
        for b in breaking:
            parts.append(f"- {b}")

    parts.append(
        "\n---\n\n"
        "Une question, un bug, une demande ? Répondez à ce mail ou écrivez à "
        "[contact@omnividens.fr](mailto:contact@omnividens.fr).\n"
    )
    return "\n".join(parts) + "\n"


def _draft_release(entry: dict[str, Any], output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    version = entry["version"]
    when = entry.get("date", date.today().isoformat())
    body = render_release_notes(entry)
    front = {
        "version": version,
        "date": when,
        "status": "drafted",
    }
    path = output_dir / f"{version}.md"
    path.write_text(
        f"---\n{yaml.safe_dump(front, allow_unicode=True, sort_keys=False)}---\n\n{body}",
        encoding="utf-8",
    )
    return path


def build_release_notes_embed(stats: ReleaseNotesStats) -> Embed:
    color = YELLOW if stats.drafted > 0 else GREEN
    fields = [
        EmbedField(name="Releases vues", value=str(stats.releases_seen), inline=True),
        EmbedField(name="Drafted", value=str(stats.drafted), inline=True),
        EmbedField(name="Déjà drafted", value=str(stats.already_done), inline=True),
    ]
    if stats.drafts:
        preview = "\n".join(f"• {d}" for d in stats.drafts[:5])
        fields.append(EmbedField(name="Drafts", value=preview, inline=False))
    return Embed(
        title=f"ReleaseNotesBot — {stats.drafted} release(s) draftée(s)",
        description=(
            "Lis `data/public/release_notes/<version>.md`, peaufine, audit `claude-judge`, publie."
            if stats.drafted > 0
            else "Aucune release en attente."
        ),
        color=color,
        fields=fields,
        footer="Argos Ops • ReleaseNotesBot",
    )


class ReleaseNotesBot(BaseAgent):
    """Drafte les release notes user-friendly depuis spec.yaml."""

    name = "ReleaseNotesBot"
    command = "/draft-release-notes"
    breaker_name = "ReleaseNotesBot"
    ai_act_risk_class = "limited"

    def __init__(
        self,
        *,
        spec_path: Path = DEFAULT_SPEC_PATH,
        output_dir: Path = DEFAULT_OUTPUT_DIR,
    ) -> None:
        self._spec_path = spec_path
        self._output_dir = output_dir

    async def run(self) -> RunResult:
        settings = get_settings()
        releases = _load_spec(self._spec_path)
        if not releases:
            logger.info(f"ReleaseNotesBot — spec absente ou vide ({self._spec_path})")
            return RunResult(status="success", output_summary="silence (no releases)")

        stats = ReleaseNotesStats(releases_seen=len(releases))
        changed = False
        for entry in releases:
            status = entry.get("status", "pending")
            if status != "pending":
                stats.already_done += 1
                continue
            version = entry.get("version")
            if not version:
                logger.warning("ReleaseNotesBot — entry sans version, skip")
                continue
            out_path = self._output_dir / f"{version}.md"
            if out_path.exists():
                stats.already_done += 1
                continue
            try:
                created = _draft_release(entry, self._output_dir)
                stats.drafted += 1
                stats.drafts.append(created.name)
                entry["status"] = "drafted"
                changed = True
            except Exception as exc:
                logger.exception(f"ReleaseNotesBot — draft {version} échec : {exc}")

        if changed:
            _persist_spec(self._spec_path, releases)

        webhook = settings.discord_webhook_ops_logs or settings.discord_webhook_alerts
        if webhook is not None and stats.drafted > 0:
            try:
                await send_embed(webhook, build_release_notes_embed(stats))
            except Exception as exc:
                logger.warning(f"ReleaseNotesBot — notif Discord échouée : {exc}")

        try:
            spec_ref = self._spec_path.relative_to(REPO_ROOT).as_posix()
        except ValueError:
            spec_ref = "data/release_notes/spec.yaml"
        try:
            out_ref = self._output_dir.relative_to(REPO_ROOT).as_posix() + "/"
        except ValueError:
            out_ref = "data/public/release_notes/"
        return RunResult(
            status="success",
            output_summary=stats.summary(),
            inputs=[
                IOItem(
                    label="Spec release notes",
                    kind="file",
                    detail=f"{stats.already_done} déjà traitées (skip)",
                    ref=spec_ref,
                    count=stats.releases_seen,
                )
            ],
            outputs=[
                IOItem(
                    label="Release notes draftées",
                    kind="draft",
                    detail="ton user-friendly · status=drafted",
                    ref=out_ref,
                    count=stats.drafted,
                )
            ],
        )


__all__ = [
    "DEFAULT_OUTPUT_DIR",
    "DEFAULT_SPEC_PATH",
    "ReleaseNotesBot",
    "ReleaseNotesStats",
    "build_release_notes_embed",
    "render_release_notes",
]
