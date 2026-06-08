"""DemoFollowupBot — Account Executive (P22.H Sales Sprint 3).

Lit ``data/sales/demos/done.yaml`` (saisi à la main après chaque démo
par le fondateur) et drafte un mail récap post-démo dans
``data/sales/demos/drafts/<id>.md``. Humain-in-the-loop strict.

Format YAML attendu (1 entrée par démo achevée) ::

    demos:
      - demo_id: "acme-2026-05-23"
        first_name: "Marc"
        when: "2026-05-23"
        pain_points:
          - "Audit RGPD passé en panique au S2 dernier"
          - "Pas de visibilité scans entre 2 audits annuels"
        next_steps:
          - ["Argos", "Envoyer un devis Pro 14j d'essai sous 48h"]
          - ["Marc", "Faire valider le budget à son board"]
        attachments: ["devis-pro-acme.pdf"]
        focus_topic: "intégration GitLab CI"
        next_milestone: "vendredi prochain"
        status: pending

Le bot patch ``status: drafted`` après création du draft. Aucun envoi
en automatique.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import yaml
from loguru import logger

from argos_ops.agents.base import BaseAgent, IOItem, RunResult
from argos_ops.config import REPO_ROOT, get_settings
from argos_ops.exceptions import AgentDataSourceError
from argos_ops.notifications.discord import (
    GREEN,
    YELLOW,
    Embed,
    EmbedField,
    send_embed,
)
from argos_ops.sales.templates import render_demo_followup

DEFAULT_DEMOS_PATH: Path = REPO_ROOT / "data" / "sales" / "demos" / "done.yaml"
DEFAULT_DRAFTS_DIR: Path = REPO_ROOT / "data" / "sales" / "demos" / "drafts"


@dataclass
class FollowupStats:
    pending_seen: int = 0
    drafts_created: int = 0
    already_done: int = 0
    drafts: list[str] = field(default_factory=list)

    def summary(self) -> str:
        return (
            f"pending={self.pending_seen} drafted={self.drafts_created} "
            f"already_done={self.already_done}"
        )


def _load_demos(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    demos = raw.get("demos", [])
    if not isinstance(demos, list):
        raise AgentDataSourceError(f"demos/done.yaml malformé : {path}")
    return demos


def _persist_demos(path: Path, demos: list[dict[str, Any]]) -> None:
    payload = {
        "updated_at": datetime.now(UTC).isoformat(),
        "demos": demos,
    }
    path.write_text(yaml.safe_dump(payload, allow_unicode=True, sort_keys=False), encoding="utf-8")


def _draft_followup(entry: dict[str, Any], drafts_dir: Path) -> Path:
    drafts_dir.mkdir(parents=True, exist_ok=True)
    when_raw = entry.get("when")
    if isinstance(when_raw, str):
        when = date.fromisoformat(when_raw)
    elif isinstance(when_raw, date):
        when = when_raw
    else:
        raise AgentDataSourceError(f"`when` invalide pour {entry.get('demo_id')}")
    next_steps_raw = entry.get("next_steps", []) or []
    next_steps: list[tuple[str, str]] = []
    for step in next_steps_raw:
        if isinstance(step, list) and len(step) == 2:
            next_steps.append((step[0], step[1]))
        else:
            raise AgentDataSourceError(
                f"`next_steps` doit être une liste de [owner, action] : {step!r}"
            )
    body = render_demo_followup(
        first_name=entry.get("first_name", "à vous"),
        when=when,
        pain_points=list(entry.get("pain_points", []) or []),
        next_steps=next_steps,
        attachments=list(entry.get("attachments", []) or []),
        focus_topic=entry.get("focus_topic", "le projet"),
        next_milestone=entry.get("next_milestone", "la semaine prochaine"),
    )
    front = {
        "demo_id": entry["demo_id"],
        "subject": f"Récap démo Argos — {when.isoformat()}",
        "to": entry.get("contact_email", "<à compléter>"),
        "attachments": list(entry.get("attachments", []) or []),
        "status": "drafted",
    }
    draft_path = drafts_dir / f"{entry['demo_id']}.md"
    draft_path.write_text(
        f"---\n{yaml.safe_dump(front, allow_unicode=True, sort_keys=False)}---\n\n{body}",
        encoding="utf-8",
    )
    return draft_path


def build_followup_embed(stats: FollowupStats) -> Embed:
    color = YELLOW if stats.drafts_created > 0 else GREEN
    fields = [
        EmbedField(name="Démos pending", value=str(stats.pending_seen), inline=True),
        EmbedField(name="Drafts créés", value=str(stats.drafts_created), inline=True),
        EmbedField(name="Déjà traités", value=str(stats.already_done), inline=True),
    ]
    if stats.drafts:
        preview = "\n".join(f"• {d}" for d in stats.drafts[:5])
        fields.append(EmbedField(name="Drafts", value=preview, inline=False))
    return Embed(
        title=f"DemoFollowupBot — {stats.drafts_created} récaps post-démo",
        description=(
            "Lis `data/sales/demos/drafts/<id>.md` et envoie via `zimbra-ops`."
            if stats.drafts_created > 0
            else "Aucun récap à drafter."
        ),
        color=color,
        fields=fields,
        footer="Argos Ops • DemoFollowupBot",
    )


class DemoFollowupBot(BaseAgent):
    """Drafte un mail récap post-démo avec pain points + next steps."""

    name = "DemoFollowupBot"
    command = "/draft-demo-followup"
    breaker_name = "DemoFollowupBot"
    ai_act_risk_class = "minimal"

    def __init__(
        self,
        *,
        demos_path: Path = DEFAULT_DEMOS_PATH,
        drafts_dir: Path = DEFAULT_DRAFTS_DIR,
    ) -> None:
        self._demos_path = demos_path
        self._drafts_dir = drafts_dir

    async def run(self) -> RunResult:
        settings = get_settings()
        demos = _load_demos(self._demos_path)
        if not demos:
            logger.info(f"DemoFollowupBot — aucun démo enregistré ({self._demos_path})")
            return RunResult(status="success", output_summary="silence (no demos)")

        stats = FollowupStats()
        changed = False
        for entry in demos:
            status = entry.get("status", "pending")
            if status != "pending":
                stats.already_done += 1
                continue
            stats.pending_seen += 1
            draft_path = self._drafts_dir / f"{entry['demo_id']}.md"
            if draft_path.exists():
                stats.already_done += 1
                continue
            try:
                created = _draft_followup(entry, self._drafts_dir)
                stats.drafts_created += 1
                stats.drafts.append(created.name)
                entry["status"] = "drafted"
                changed = True
            except Exception as exc:
                logger.exception(f"DemoFollowupBot — {entry.get('demo_id')} échec : {exc}")

        if changed:
            _persist_demos(self._demos_path, demos)

        webhook = settings.discord_webhook_ops_logs or settings.discord_webhook_alerts
        if webhook is not None:
            try:
                await send_embed(webhook, build_followup_embed(stats))
            except Exception as exc:
                logger.warning(f"DemoFollowupBot — notif Discord échouée : {exc}")

        inputs = [
            IOItem(
                label="Démos achevées",
                kind="file",
                detail=f"{stats.pending_seen} pending · {stats.already_done} déjà traité(s)",
                ref="data/sales/demos/done.yaml",
                count=len(demos),
            )
        ]
        outputs: list[IOItem] = []
        if stats.drafts_created:
            outputs.append(
                IOItem(
                    label="Mails récap post-démo draftés",
                    kind="draft",
                    detail="; ".join(stats.drafts[:5]),
                    ref="data/sales/demos/drafts/",
                    count=stats.drafts_created,
                )
            )

        return RunResult(
            status="success",
            output_summary=stats.summary(),
            inputs=inputs,
            outputs=outputs,
        )


__all__ = [
    "DEFAULT_DEMOS_PATH",
    "DEFAULT_DRAFTS_DIR",
    "DemoFollowupBot",
    "FollowupStats",
    "build_followup_embed",
]
