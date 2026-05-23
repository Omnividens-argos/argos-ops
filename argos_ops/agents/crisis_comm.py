"""CrisisCommBot — réponses type prêtes en cas d'incident public.

Bibliothèque de templates de réponse de crise + matcher qui sélectionne
le template pertinent selon ``incident_type``. Les templates sont
volontairement courts et neutres, ils servent de point de départ — le
founder personnalise avant publication.

Pipeline shadow :

1. Lit ``data/comm/crisis_incidents.yaml`` (incidents enregistrés)
2. Pour les incidents ``status: open``, matche le bon template
3. Drafte une réponse dans ``data/comm/crisis_drafts/<incident_id>.md``
4. Alerte Discord rouge SI incident ``severity: critical``
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml
from loguru import logger

from argos_ops.agents.base import BaseAgent, RunResult
from argos_ops.comm.brand import CANONICAL_DOMAIN
from argos_ops.config import REPO_ROOT, get_settings
from argos_ops.notifications.discord import (
    GREEN,
    RED,
    YELLOW,
    Embed,
    EmbedField,
    send_embed,
)

INCIDENTS_PATH = REPO_ROOT / "data" / "comm" / "crisis_incidents.yaml"
DRAFTS_DIR = REPO_ROOT / "data" / "comm" / "crisis_drafts"


TEMPLATES: dict[str, str] = {
    "data_breach": (
        "Nous avons identifié un incident affectant {scope}. "
        "Nos équipes ont confiné l'incident à {time}. Aucune donnée client "
        "n'a, à ce stade, été exfiltrée. Nous communiquerons la CNIL dans "
        "le délai légal de 72h. Plus d'informations : "
        f"https://{CANONICAL_DOMAIN}/incidents/{{slug}}"
    ),
    "service_down": (
        "Argos rencontre actuellement une indisponibilité partielle. "
        "Statut en temps réel sur https://status.omnividens.fr. "
        "Désolés pour la gêne occasionnée — nos équipes travaillent à "
        "restaurer le service au plus vite."
    ),
    "false_finding_dispute": (
        "Nous prenons votre retour très au sérieux. Un finding contesté "
        "sera ré-audité manuellement sous 48h ouvrées. Si confirmé faux "
        "positif, nous mettrons à jour notre moteur et vous re-livrerons "
        "le rapport corrigé."
    ),
    "negative_press": (
        "Nous avons pris connaissance de l'article et restons à disposition "
        "pour échanger directement avec les journalistes. Notre engagement "
        "est consultable sur https://"
        + CANONICAL_DOMAIN
        + "/engagements."
    ),
}


@dataclass
class CrisisIncident:
    id: str
    incident_type: str
    severity: str  # 'critical' | 'major' | 'minor'
    scope: str = ""
    time: str = ""
    notes: str = ""
    status: str = "open"


@dataclass
class CrisisStats:
    total: int = 0
    open_count: int = 0
    drafted: int = 0
    critical_open: int = 0

    def summary(self) -> str:
        return (
            f"total={self.total} open={self.open_count} "
            f"drafted={self.drafted} critical={self.critical_open}"
        )


def load_incidents(path: Path | None = None) -> list[CrisisIncident]:
    path = path or INCIDENTS_PATH
    if not path.exists():
        return []
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    out: list[CrisisIncident] = []
    for entry in raw.get("incidents", []):
        if not isinstance(entry, dict):
            continue
        try:
            out.append(
                CrisisIncident(
                    id=str(entry["id"]),
                    incident_type=str(entry["incident_type"]),
                    severity=str(entry.get("severity", "minor")),
                    scope=str(entry.get("scope", "")),
                    time=str(entry.get("time", "")),
                    notes=str(entry.get("notes", "")),
                    status=str(entry.get("status", "open")),
                )
            )
        except KeyError:
            continue
    return out


def select_template(incident_type: str) -> str:
    return TEMPLATES.get(incident_type, "_Type d'incident non reconnu — drafter manuellement._")


def draft_response(incident: CrisisIncident) -> str:
    template = select_template(incident.incident_type)
    rendered = template.format(
        scope=incident.scope or "(à préciser)",
        time=incident.time or "(à préciser)",
        slug=incident.id,
    )
    return (
        f"---\nstatus: drafted\nincident_id: {incident.id}\n"
        f"incident_type: {incident.incident_type}\n"
        f"severity: {incident.severity}\n---\n\n"
        f"# Réponse type — {incident.id}\n\n"
        f"## Template appliqué\n\n{rendered}\n\n"
        f"## Notes founder\n\n{incident.notes or '_(à compléter)_'}\n\n"
        f"## À valider AVANT publication\n\n"
        f"- [ ] Faits relus et confirmés par le founder\n"
        f"- [ ] CNIL informée si data_breach (délai 72h)\n"
        f"- [ ] Clients impactés notifiés en direct AVANT la com publique\n"
    )


def build_crisis_embed(stats: CrisisStats) -> Embed:
    if stats.critical_open > 0:
        color = RED
    elif stats.open_count > 0:
        color = YELLOW
    else:
        color = GREEN
    return Embed(
        title=f"Argos — CrisisCommBot ({stats.open_count} ouverts)",
        color=color,
        fields=[
            EmbedField(name="Total", value=str(stats.total), inline=True),
            EmbedField(name="Ouverts", value=str(stats.open_count), inline=True),
            EmbedField(name="Draftés", value=str(stats.drafted), inline=True),
            EmbedField(name="Critiques", value=str(stats.critical_open), inline=True),
        ],
        footer="Argos Ops • CrisisCommBot",
    )


class CrisisCommBot(BaseAgent):
    """Drafte des réponses type pour les incidents ouverts."""

    name = "CrisisCommBot"
    command = "/draft-crisis-response"
    breaker_name = "CrisisCommBot"

    async def run(self) -> RunResult:
        incidents = load_incidents()
        stats = CrisisStats(total=len(incidents))
        open_inc = [i for i in incidents if i.status == "open"]
        stats.open_count = len(open_inc)
        stats.critical_open = sum(1 for i in open_inc if i.severity == "critical")

        DRAFTS_DIR.mkdir(parents=True, exist_ok=True)
        for incident in open_inc:
            path = DRAFTS_DIR / f"{incident.id}.md"
            if path.exists():
                continue
            try:
                path.write_text(draft_response(incident), encoding="utf-8")
                stats.drafted += 1
            except OSError as exc:
                logger.warning(f"CrisisCommBot — écriture {incident.id} : {exc}")

        settings = get_settings()
        webhook = settings.discord_webhook_alerts or settings.discord_webhook_ops_logs
        if webhook is not None and stats.open_count > 0:
            try:
                await send_embed(webhook, build_crisis_embed(stats))
            except Exception as exc:
                logger.warning(f"CrisisCommBot — notif Discord : {exc}")

        return RunResult(status="success", output_summary=stats.summary())


__all__ = [
    "DRAFTS_DIR",
    "INCIDENTS_PATH",
    "TEMPLATES",
    "CrisisCommBot",
    "CrisisIncident",
    "CrisisStats",
    "build_crisis_embed",
    "draft_response",
    "load_incidents",
    "select_template",
]
