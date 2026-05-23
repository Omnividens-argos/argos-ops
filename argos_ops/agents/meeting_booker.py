"""MeetingBooker — Sales Ops (P22.H Sales Sprint 3).

Lit ``data/sales/meetings/requests.yaml`` (rempli à la main par le
fondateur ou via réponse EmailBot), génère un draft d'invitation iCal
+ email de confirmation, et patch le statut à ``confirmed``.

Le draft email est rangé dans ``data/sales/meetings/drafts/<id>.md``
avec frontmatter (sujet, destinataire, attachment ICS) — le fondateur
valide à la main et envoie via ``zimbra-ops`` ou répond à
``/send-outbound-batch`` qui inclut MeetingBooker en option future.

Pas d'envoi automatique en Sprint 3 — humain-in-the-loop strict.
Discord notification pour signaler les nouveaux drafts.
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml
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
from argos_ops.sales.ical import build_ical_invite
from argos_ops.sales.models import MeetingRequest

DEFAULT_REQUESTS_PATH: Path = REPO_ROOT / "data" / "sales" / "meetings" / "requests.yaml"
DEFAULT_DRAFTS_DIR: Path = REPO_ROOT / "data" / "sales" / "meetings" / "drafts"


@dataclass
class BookingStats:
    pending_seen: int = 0
    drafts_created: int = 0
    already_done: int = 0
    drafts: list[str] = field(default_factory=list)

    def summary(self) -> str:
        return (
            f"pending={self.pending_seen} drafted={self.drafts_created} "
            f"already_done={self.already_done}"
        )


def _load_requests(path: Path) -> list[MeetingRequest]:
    """Charge les demandes de RDV depuis le YAML."""
    if not path.exists():
        return []
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    requests_raw = raw.get("requests", [])
    out: list[MeetingRequest] = []
    for entry in requests_raw:
        starts_at_raw = entry["starts_at"]
        if isinstance(starts_at_raw, str):
            starts_at = datetime.fromisoformat(starts_at_raw)
        elif isinstance(starts_at_raw, datetime):
            starts_at = starts_at_raw
        else:
            raise ValueError(f"starts_at invalide pour {entry.get('request_id')}")
        if starts_at.tzinfo is None:
            starts_at = starts_at.replace(tzinfo=UTC)
        out.append(
            MeetingRequest(
                request_id=entry["request_id"],
                attendee_email=entry["attendee_email"],
                attendee_name=entry.get("attendee_name", ""),
                company=entry.get("company", ""),
                starts_at=starts_at,
                duration_minutes=int(entry.get("duration_minutes", 30)),
                location=entry.get("location", "Visio (Jitsi / Whereby — lien envoyé H-2)"),
                status=entry.get("status", "pending"),
            )
        )
    return out


def _persist_requests(path: Path, requests: list[MeetingRequest]) -> None:
    """Réécrit le YAML avec les statuts mis à jour."""
    payload: dict[str, Any] = {
        "updated_at": datetime.now(UTC).isoformat(),
        "requests": [
            {
                "request_id": r.request_id,
                "attendee_email": r.attendee_email,
                "attendee_name": r.attendee_name,
                "company": r.company,
                "starts_at": r.starts_at.isoformat(),
                "duration_minutes": r.duration_minutes,
                "location": r.location,
                "status": r.status,
            }
            for r in requests
        ],
    }
    path.write_text(yaml.safe_dump(payload, allow_unicode=True, sort_keys=False), encoding="utf-8")


def _draft_meeting_email(
    request: MeetingRequest,
    *,
    organizer_email: str,
    organizer_name: str,
    drafts_dir: Path,
) -> Path:
    """Crée le draft email + attachment ICS pour une demande de RDV."""
    drafts_dir.mkdir(parents=True, exist_ok=True)
    uid = f"argos-{request.request_id}-{secrets.token_hex(4)}@omnividens.fr"
    summary = f"Argos — démo avec {request.company}"
    description = (
        "Démo Argos (15-25 min sur la partie scan + 5-10 min Q&A).\n\n"
        "Si le créneau ne convient plus, répondez à ce mail avec une "
        "alternative — je m'adapte."
    )
    ics = build_ical_invite(
        uid=uid,
        starts_at=request.starts_at,
        duration_minutes=request.duration_minutes,
        summary=summary,
        description=description,
        location=request.location,
        organizer_email=organizer_email,
        organizer_name=organizer_name,
        attendee_email=request.attendee_email,
        attendee_name=request.attendee_name,
    )
    ics_path = drafts_dir / f"{request.request_id}.ics"
    ics_path.write_text(ics, encoding="utf-8")

    starts_local = request.starts_at.astimezone(UTC)
    body = (
        f"Bonjour {request.attendee_name or 'à vous'},\n\n"
        f"Confirmation du créneau pour la démo Argos :\n\n"
        f"- **Quand** : {starts_local.strftime('%A %d %B %Y à %H:%M UTC')}\n"
        f"- **Durée** : {request.duration_minutes} minutes\n"
        f"- **Où** : {request.location}\n\n"
        f"L'invitation iCalendar est en pièce jointe ({ics_path.name}). "
        f"Le lien visio arrive H-2 par mail.\n\n"
        f"Si autre chose à creuser avant le RDV, n'hésitez pas — répondez "
        f"à ce mail.\n\n"
        f"À très vite,\n"
        f"Le fondateur d'Omnividens\n"
    )
    front = {
        "request_id": request.request_id,
        "to": request.attendee_email,
        "subject": f"Démo Argos confirmée — {starts_local.strftime('%d/%m %H:%M UTC')}",
        "attachment": ics_path.name,
        "uid": uid,
        "status": "drafted",
    }
    draft_path = drafts_dir / f"{request.request_id}.md"
    draft_path.write_text(
        f"---\n{yaml.safe_dump(front, allow_unicode=True, sort_keys=False)}---\n\n{body}",
        encoding="utf-8",
    )
    return draft_path


def build_booking_embed(stats: BookingStats) -> Embed:
    color = YELLOW if stats.drafts_created > 0 else GREEN
    fields = [
        EmbedField(name="Demandes pending", value=str(stats.pending_seen), inline=True),
        EmbedField(name="Drafts créés", value=str(stats.drafts_created), inline=True),
        EmbedField(name="Déjà traités", value=str(stats.already_done), inline=True),
    ]
    if stats.drafts:
        preview = "\n".join(f"• {d}" for d in stats.drafts[:5])
        fields.append(EmbedField(name="Drafts", value=preview, inline=False))
    return Embed(
        title=f"MeetingBooker — {stats.drafts_created} drafts RDV",
        description=(
            "Lis `data/sales/meetings/drafts/<id>.md` et envoie via `zimbra-ops` après validation."
            if stats.drafts_created > 0
            else "Aucune nouvelle demande à confirmer."
        ),
        color=color,
        fields=fields,
        footer="Argos Ops • MeetingBooker",
    )


class MeetingBooker(BaseAgent):
    """Confirme les demandes de RDV démo (draft email + ICS, humain valide)."""

    name = "MeetingBooker"
    command = "/book-meeting"
    breaker_name = "MeetingBooker"

    def __init__(
        self,
        *,
        requests_path: Path = DEFAULT_REQUESTS_PATH,
        drafts_dir: Path = DEFAULT_DRAFTS_DIR,
    ) -> None:
        self._requests_path = requests_path
        self._drafts_dir = drafts_dir

    async def run(self) -> RunResult:
        settings = get_settings()
        requests = _load_requests(self._requests_path)
        if not requests:
            logger.info(f"MeetingBooker — aucune demande ({self._requests_path})")
            return RunResult(status="success", output_summary="silence (no requests)")

        organizer_email = settings.email_user or "contact@omnividens.fr"
        organizer_name = settings.email_reply_name
        stats = BookingStats()
        for request in requests:
            if request.status != "pending":
                stats.already_done += 1
                continue
            stats.pending_seen += 1
            draft_path = self._drafts_dir / f"{request.request_id}.md"
            if draft_path.exists():
                stats.already_done += 1
                continue
            try:
                created = _draft_meeting_email(
                    request,
                    organizer_email=organizer_email,
                    organizer_name=organizer_name,
                    drafts_dir=self._drafts_dir,
                )
                stats.drafts_created += 1
                stats.drafts.append(created.name)
                request.status = "drafted"
            except Exception as exc:
                logger.exception(f"MeetingBooker — draft {request.request_id} échec : {exc}")

        if stats.drafts_created > 0:
            _persist_requests(self._requests_path, requests)

        webhook = settings.discord_webhook_ops_logs or settings.discord_webhook_alerts
        if webhook is not None:
            try:
                await send_embed(webhook, build_booking_embed(stats))
            except Exception as exc:
                logger.warning(f"MeetingBooker — notif Discord échouée : {exc}")

        return RunResult(status="success", output_summary=stats.summary())


__all__ = [
    "DEFAULT_DRAFTS_DIR",
    "DEFAULT_REQUESTS_PATH",
    "BookingStats",
    "MeetingBooker",
    "build_booking_embed",
]
