"""OutboundBot LIVE — envoi SMTP des touches drafted (P13.B Sprint 3).

Successeur de l'agent ``OutboundBot`` shadow (qui reste en place pour le
scaffold) : itère les séquences scaffold + drafted dans
``data/outbound/sequences/`` et **envoie réellement** les touches dont
``scheduled_date <= today`` via Zimbra SMTP.

Deux modes (cf. P22.H prompt 6) :

- ``stage`` (par défaut, *fallback* si ``OUTBOUND_FROM_DOMAIN`` absent) —
  l'expéditeur est l'email canonique Argos
  (``settings.email_user`` = ``contact@omnividens.fr``) et le
  destinataire est **rerouté vers cette même boîte** pour audit
  manuel. Permet de valider tout le pipeline (rendering, footer,
  threading) sans toucher à la réputation du domaine officiel ni à
  l'inbox du lead.
- ``live`` (requiert ``OUTBOUND_LIVE_MODE=true`` ET
  ``OUTBOUND_FROM_DOMAIN=<domaine.secondaire>`` ET
  ``OUTBOUND_UNSUBSCRIBE_SECRET`` non vide) — l'expéditeur passe sur le
  domaine secondaire warmé-up et l'email part vers le lead réel.

Garde-fous métier :

- Breaker ``outbound_volume_exceeded`` cap par le ``OUTBOUND_DAILY_MAX``
- Footer RGPD + AI Act + opt-out HMAC obligatoire (P17)
- Touches drafted seulement (jamais scaffold sans body)
- Idempotence forte : ``touch.status='sent' + sent_at`` patché dans
  ``meta.yaml`` avant retour, pas de double envoi possible
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

import yaml
from loguru import logger

from argos_ops.agents.base import BaseAgent, IOItem, RunResult
from argos_ops.config import REPO_ROOT, Settings, get_settings
from argos_ops.integrations.zimbra import send_email
from argos_ops.notifications.discord import (
    GREEN,
    ORANGE,
    YELLOW,
    Embed,
    EmbedField,
    send_embed,
)
from argos_ops.outbound.models import SequenceState
from argos_ops.outbound.sequence import SEQUENCES_DIR, load_sequence_state
from argos_ops.outbound.templates import build_footer

SendMode = Literal["stage", "live", "disabled"]


@dataclass
class SendStats:
    sequences_scanned: int = 0
    touches_ready: int = 0
    touches_sent: int = 0
    touches_skipped_no_body: int = 0
    touches_skipped_already_sent: int = 0
    failures: int = 0
    sent_slugs: list[str] = field(default_factory=list)

    def summary(self) -> str:
        return (
            f"seq={self.sequences_scanned} ready={self.touches_ready} "
            f"sent={self.touches_sent} no_body={self.touches_skipped_no_body} "
            f"already_sent={self.touches_skipped_already_sent} fail={self.failures}"
        )


def determine_mode(settings: Settings) -> SendMode:
    """Décide entre ``stage`` / ``live`` / ``disabled`` selon la config.

    - ``disabled`` si ``email_user`` ou ``email_password`` manquent — on
      ne peut pas se connecter au SMTP, autant échouer tôt.
    - ``live`` si ``outbound_live_mode=True`` + ``outbound_from_domain``
      non vide + ``outbound_unsubscribe_secret`` présent.
    - ``stage`` sinon (mode par défaut tant que le domaine secondaire
      n'est pas acquis).
    """
    if settings.email_user is None or settings.email_password is None:
        return "disabled"
    if (
        settings.outbound_live_mode
        and settings.outbound_from_domain
        and settings.outbound_unsubscribe_secret is not None
    ):
        return "live"
    return "stage"


def _read_meta(meta_path: Path) -> dict[str, Any]:
    loaded = yaml.safe_load(meta_path.read_text(encoding="utf-8")) or {}
    return loaded if isinstance(loaded, dict) else {}


def _write_meta(meta_path: Path, payload: dict[str, Any]) -> None:
    meta_path.write_text(
        yaml.safe_dump(payload, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


def _read_touch_md(touch_path: Path) -> tuple[dict[str, Any], str]:
    """Lit un touch_N.md → ``(frontmatter, body)``."""
    raw = touch_path.read_text(encoding="utf-8")
    if not raw.startswith("---\n"):
        return {}, raw
    try:
        _, front_block, body = raw.split("---\n", 2)
    except ValueError:
        return {}, raw
    front = yaml.safe_load(front_block) or {}
    return front, body.lstrip("\n")


def build_outbound_embed(stats: SendStats, mode: SendMode) -> Embed:
    if stats.failures > 0:
        color = ORANGE
    elif stats.touches_sent > 0:
        color = YELLOW
    else:
        color = GREEN
    mode_label = {
        "stage": "stage (rerouté → contact@omnividens.fr)",
        "live": "live (domaine secondaire actif)",
        "disabled": "disabled (credentials SMTP manquants)",
    }[mode]
    fields = [
        EmbedField(name="Mode", value=mode_label, inline=False),
        EmbedField(name="Séquences scannées", value=str(stats.sequences_scanned), inline=True),
        EmbedField(name="Touches prêtes", value=str(stats.touches_ready), inline=True),
        EmbedField(name="Envoyées", value=str(stats.touches_sent), inline=True),
        EmbedField(name="Sans body", value=str(stats.touches_skipped_no_body), inline=True),
        EmbedField(name="Échecs", value=str(stats.failures), inline=True),
    ]
    if stats.sent_slugs:
        preview = "\n".join(f"• {s}" for s in stats.sent_slugs[:5])
        fields.append(EmbedField(name="Slugs envoyés", value=preview, inline=False))
    title = f"OutboundBot LIVE — {stats.touches_sent} envoyées ({mode})"
    return Embed(
        title=title,
        description=(
            "Touches outbound poussées sur SMTP. Vérifie Sent / Drafts si stage."
            if stats.touches_sent > 0
            else "Aucune touche prête à envoyer aujourd'hui."
        ),
        color=color,
        fields=fields,
        footer="Argos Ops • OutboundBot LIVE",
    )


class OutboundSender(BaseAgent):
    """Envoi SMTP réel des touches drafted (P13.B — stage/live)."""

    name = "OutboundSender"
    command = "/send-outbound-batch"
    breaker_name = "OutboundBot"  # partage le breaker avec OutboundBot shadow

    def __init__(self, *, sequences_dir: Path = SEQUENCES_DIR) -> None:
        self._sequences_dir = sequences_dir

    async def run(self) -> RunResult:
        settings = get_settings()
        mode = determine_mode(settings)
        if mode == "disabled":
            return RunResult(
                status="failed",
                error=(
                    "OutboundSender — EMAIL_USER ou EMAIL_PASSWORD manquant. "
                    "Configure Zimbra avant tout envoi (D-018)."
                ),
            )

        if not self._sequences_dir.exists():
            logger.info(f"OutboundSender — pas de dossier {self._sequences_dir}")
            return RunResult(status="success", output_summary="silence (no sequences)")

        today = datetime.now(UTC).date()
        stats = SendStats()
        secret_obj = settings.outbound_unsubscribe_secret
        secret = secret_obj.get_secret_value() if secret_obj is not None else ""

        # En live mode l'expéditeur devra passer sur le domaine secondaire
        # (`argos@<OUTBOUND_FROM_DOMAIN>`) — ça demandera d'étendre
        # `zimbra.send_email` pour découpler SMTP login (Zimbra user)
        # de l'adresse From visible. À traiter au flip live effectif
        # (cf. data/p22-sessions/PROMPT-6-decisions.md D-023). Pour
        # l'instant on garde l'expéditeur Zimbra dans les deux modes.
        from_name = settings.email_reply_name

        sent_count_today = 0
        for seq_dir in sorted(self._sequences_dir.iterdir()):
            if not seq_dir.is_dir():
                continue
            meta_path = seq_dir / "meta.yaml"
            if not meta_path.exists():
                continue
            stats.sequences_scanned += 1
            try:
                state = load_sequence_state(seq_dir.name, root=self._sequences_dir)
            except (FileNotFoundError, ValueError) as exc:
                logger.warning(f"OutboundSender — meta corrompu {seq_dir.name} : {exc}")
                stats.failures += 1
                continue

            real_recipient = self._extract_recipient(state, seq_dir)
            for touch in state.touches:
                if touch.scheduled_date > today:
                    continue
                if touch.status == "sent":
                    stats.touches_skipped_already_sent += 1
                    continue
                if touch.status != "drafted" or not touch.body or not touch.subject:
                    stats.touches_skipped_no_body += 1
                    continue
                stats.touches_ready += 1
                if sent_count_today >= settings.outbound_daily_max:
                    logger.info(
                        f"OutboundSender — daily cap {settings.outbound_daily_max} atteint, "
                        "arrêt anticipé"
                    )
                    break

                to_address = real_recipient if mode == "live" else (settings.email_user or "")
                subject = touch.subject if mode == "live" else f"[STAGE] {touch.subject}"
                footer = build_footer(
                    email=real_recipient,
                    secret=secret,
                    tagline=settings.email_signature_tagline,
                    site_url=settings.email_signature_site_url,
                    ai_disclosure=settings.email_signature_ai_disclosure,
                )
                body = (touch.body or "") + footer
                try:
                    assert settings.email_password is not None
                    await send_email(
                        host=settings.email_smtp_host,
                        port=settings.email_smtp_port,
                        user=settings.email_user or "",
                        password=settings.email_password,
                        from_name=from_name,
                        to=to_address,
                        subject=subject,
                        body_text=body,
                        include_signature=False,  # footer déjà ajouté
                    )
                    touch.status = "sent"
                    touch.sent_at = datetime.now(UTC).isoformat()
                    stats.touches_sent += 1
                    sent_count_today += 1
                    stats.sent_slugs.append(f"{seq_dir.name}#{int(touch.step)}")
                except Exception as exc:
                    logger.exception(
                        f"OutboundSender — envoi {seq_dir.name}#{int(touch.step)} échec : {exc}"
                    )
                    stats.failures += 1

            if any(t.status == "sent" for t in state.touches):
                _persist_state(meta_path, state)

            if sent_count_today >= settings.outbound_daily_max:
                break

        webhook = settings.discord_webhook_ops_logs or settings.discord_webhook_alerts
        if webhook is not None and stats.sequences_scanned > 0:
            try:
                await send_embed(webhook, build_outbound_embed(stats, mode))
            except Exception as exc:
                logger.warning(f"OutboundSender — notif Discord échouée : {exc}")

        try:
            seq_ref = self._sequences_dir.relative_to(REPO_ROOT).as_posix() + "/"
        except ValueError:
            seq_ref = "data/outbound/sequences/"
        dest_label = (
            "envoyés au lead réel"
            if mode == "live"
            else f"reroutés → {settings.email_user} (stage)"
        )
        return RunResult(
            status="success",
            output_summary=stats.summary(),
            inputs=[
                IOItem(
                    label="Séquences outbound drafted",
                    kind="file",
                    detail=f"touches dues (scheduled_date <= today) · {stats.touches_ready} prêtes",
                    ref=seq_ref,
                    count=stats.sequences_scanned,
                )
            ],
            outputs=[
                IOItem(
                    label="Emails outbound envoyés (SMTP)",
                    kind="email",
                    detail=f"mode {mode} · {dest_label} · {stats.failures} échecs",
                    count=stats.touches_sent,
                )
            ],
        )

    def _extract_recipient(self, state: SequenceState, seq_dir: Path) -> str:
        """Récupère le destinataire réel : 1er email_guess de l'enriched, sinon fallback."""
        enriched_path = (
            seq_dir.parent.parent.parent / state.enriched_path
            if state.enriched_path and not Path(state.enriched_path).is_absolute()
            else Path(state.enriched_path)
            if state.enriched_path
            else None
        )
        if enriched_path and enriched_path.exists():
            raw = enriched_path.read_text(encoding="utf-8")
            if raw.startswith("---\n"):
                try:
                    _, front_block, _ = raw.split("---\n", 2)
                    front = yaml.safe_load(front_block) or {}
                    guesses = front.get("email_guesses") or []
                    if guesses:
                        email = guesses[0]["email"]
                        return str(email) if email is not None else f"contact@{state.domain}"
                except (ValueError, KeyError, TypeError):
                    pass
        # Fallback déterministe basé sur le slug : firstname.lastname@domain
        parts = state.full_name.lower().split()
        if len(parts) >= 2:
            return f"{parts[0]}.{parts[-1]}@{state.domain}"
        return f"contact@{state.domain}"


def _persist_state(meta_path: Path, state: SequenceState) -> None:
    """Réécrit meta.yaml après mise à jour de touches."""
    payload = {
        "lead_slug": state.lead_slug,
        "full_name": state.full_name,
        "domain": state.domain,
        "enriched_path": state.enriched_path,
        "opt_out_token": state.opt_out_token,
        "sequence_status": state.sequence_status,
        "created_at": state.created_at,
        "notes": state.notes,
        "touches": [
            {
                "step": int(t.step),
                "scheduled_date": t.scheduled_date.isoformat(),
                "status": t.status,
                "subject": t.subject,
                "body": t.body,
                "judge_score": t.judge_score,
                "judge_verdict": t.judge_verdict,
                "sent_at": t.sent_at,
            }
            for t in state.touches
        ],
    }
    _write_meta(meta_path, payload)


__all__ = [
    "OutboundSender",
    "SendMode",
    "SendStats",
    "build_outbound_embed",
    "determine_mode",
]
