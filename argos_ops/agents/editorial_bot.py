"""EditorialBot — chef d'orchestre éditorial du Sprint contenu.

Lit le **dernier digest TrendSpotter** (``data/trends/digest-<date>.md``,
une liste numérotée de sujets cyber chauds), et pour chaque sujet **choisit
un canal + un angle** puis écrit une **liste de tâches** dans
``data/editorial/queue-<date>.yaml`` :

    « lancer le writer X (slash /draft-X) sur le sujet Y, angle Z »

EditorialBot **ne lance pas** les writers lui-même (mode shadow) : il
recommande. Le fondateur déclenche ensuite manuellement les ``/draft-*``
listés. C'est volontaire — le drafting reste humain-in-the-loop.

Répartition des canaux :
- Un sujet « grand public » (phishing, ransomware, mot de passe…) part sur
  **Meta** (persona TPE/PME, cf. ``meta-writer``).
- Les autres tournent sur LinkedIn / Mastodon / Bluesky / X (round-robin)
  pour éviter de tout concentrer sur un canal.
- **Truth Social est exclu** par défaut : canal expérimental + brand safety
  apolitique stricte → mauvais fit pour un sujet cyber chaud arbitraire.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import yaml
from loguru import logger

from argos_ops.agents.base import BaseAgent, IOItem, RunResult
from argos_ops.config import REPO_ROOT, get_settings
from argos_ops.notifications.discord import GREEN, YELLOW, Embed, EmbedField, send_embed

TRENDS_DIR = REPO_ROOT / "data" / "trends"
QUEUE_DIR = REPO_ROOT / "data" / "editorial"

# Plafond de tâches recommandées par run (le digest est déjà un top-5).
MAX_TASKS = 5

# Canaux pour les sujets non grand-public, en round-robin (Truth exclu).
_CHANNEL_ROTATION = ("linkedin", "mastodon", "bluesky", "x")

# Heuristique « grand public » → MetaWriter (persona TPE/PME non technique).
_GRAND_PUBLIC_KEYWORDS = (
    "phishing",
    "hameçonnage",
    "ransomware",
    "rançongiciel",
    "arnaque",
    "mot de passe",
    "sauvegarde",
    "fuite de données",
)

# canal -> (writer, slash, gabarit d'angle)
_CHANNEL_META: dict[str, tuple[str, str, str]] = {
    "linkedin": (
        "linkedin-writer",
        "/draft-linkedin",
        "Angle décideur : relier le sujet à une objection RSSI/CTO, CTA soft.",
    ),
    "mastodon": (
        "mastodon-writer",
        "/draft-mastodon",
        "Angle technique infosec : partage utile d'abord, pas de promo directe.",
    ),
    "bluesky": (
        "bluesky-writer",
        "/draft-bluesky",
        "Angle tech early-adopter : hook punchy + 1 hashtag.",
    ),
    "x": (
        "x-writer",
        "/draft-x",
        "Angle viral cyber : hook scroll-stopper, ≤280 chars.",
    ),
    "meta": (
        "meta-writer",
        "/draft-meta",
        "Angle grand public rassurant : vulgariser, anti-FUD, CTA tier d'entrée.",
    ),
}

_TOPIC_RE = re.compile(r"^\s*\d+\.\s+(.+?)\s*$")


@dataclass
class EditorialPlan:
    """Plan éditorial produit par un run."""

    source_digest: Path | None
    tasks: list[dict[str, str]]
    queue_path: Path | None

    def summary(self) -> str:
        src = "yes" if self.source_digest else "none"
        return f"digest={src} tasks={len(self.tasks)}"


def find_latest_digest(trends_dir: Path) -> Path | None:
    """Retourne le digest TrendSpotter le plus récent, ou None."""
    if not trends_dir.exists():
        return None
    digests = sorted(trends_dir.glob("digest-*.md"))
    return digests[-1] if digests else None


def parse_digest_topics(path: Path) -> list[str]:
    """Extrait les titres de sujets d'un digest (liste numérotée)."""
    topics: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        match = _TOPIC_RE.match(line)
        if match:
            topics.append(match.group(1).strip())
    return topics


def _is_grand_public(topic: str) -> bool:
    low = topic.lower()
    return any(keyword in low for keyword in _GRAND_PUBLIC_KEYWORDS)


def assign_tasks(topics: list[str]) -> list[dict[str, str]]:
    """Associe à chaque sujet un canal + writer + angle (recommandation)."""
    tasks: list[dict[str, str]] = []
    rotation_index = 0
    for topic in topics:
        if _is_grand_public(topic):
            channel = "meta"
        else:
            channel = _CHANNEL_ROTATION[rotation_index % len(_CHANNEL_ROTATION)]
            rotation_index += 1
        writer, slash, angle = _CHANNEL_META[channel]
        tasks.append(
            {
                "topic": topic,
                "channel": channel,
                "writer": writer,
                "slash": slash,
                "angle": angle,
            }
        )
    return tasks


def build_queue_doc(
    tasks: list[dict[str, str]], *, source_digest: Path | None, now: datetime
) -> dict[str, object]:
    """Construit le document YAML de la queue éditoriale."""
    return {
        "generated_at": now.isoformat(),
        "source_digest": source_digest.name if source_digest else None,
        # EditorialBot recommande, il ne lance pas les writers (humain-in-the-loop).
        "mode": "shadow",
        "tasks": tasks,
    }


def write_queue(doc: dict[str, object], *, now: datetime, out_dir: Path) -> Path:
    """Écrit la queue dans out_dir/queue-YYYY-MM-DD.yaml."""
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"queue-{now.date().isoformat()}.yaml"
    path.write_text(yaml.safe_dump(doc, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return path


def build_editorial_embed(plan: EditorialPlan) -> Embed:
    color = GREEN if plan.tasks else YELLOW
    lines = [f"• {t['slash']} — {t['topic']}" for t in plan.tasks[:MAX_TASKS]]
    fields = [
        EmbedField(name="Recommandations", value="\n".join(lines) or "—", inline=False),
        EmbedField(
            name="Queue",
            value=plan.queue_path.name if plan.queue_path else "—",
            inline=True,
        ),
    ]
    return Embed(
        title="Argos — EditorialBot",
        color=color,
        fields=fields,
        footer="Argos Ops • EditorialBot",
    )


class EditorialBot(BaseAgent):
    """Chef d'orchestre éditorial : digest TrendSpotter → queue de recommandations."""

    name = "EditorialBot"
    command = "/run-editorial"
    breaker_name = "EditorialBot"
    ai_act_risk_class = "minimal"

    async def run(self) -> RunResult:
        digest = find_latest_digest(TRENDS_DIR)
        if digest is None:
            logger.info("EditorialBot — aucun digest TrendSpotter trouvé (rien à planifier).")
            return RunResult(status="success", output_summary="digest=none tasks=0")

        topics = parse_digest_topics(digest)
        if len(topics) > MAX_TASKS:
            logger.info(f"EditorialBot — {len(topics)} sujets, tronqué à {MAX_TASKS}.")
            topics = topics[:MAX_TASKS]
        tasks = assign_tasks(topics)

        now = datetime.now(UTC)
        queue_path: Path | None = None
        if tasks:
            doc = build_queue_doc(tasks, source_digest=digest, now=now)
            queue_path = write_queue(doc, now=now, out_dir=QUEUE_DIR)

        plan = EditorialPlan(source_digest=digest, tasks=tasks, queue_path=queue_path)

        settings = get_settings()
        webhook = settings.discord_webhook_content or settings.discord_webhook_ops_logs
        if webhook is not None and tasks:
            try:
                await send_embed(webhook, build_editorial_embed(plan))
            except Exception as exc:
                logger.warning(f"EditorialBot — notif Discord a échoué : {exc}")

        inputs = [
            IOItem(
                label="Dernier digest TrendSpotter",
                kind="file",
                detail=f"{len(topics)} sujet(s) chaud(s)",
                ref=f"data/trends/{digest.name}",
                count=len(topics),
            )
        ]
        outputs: list[IOItem] = []
        if queue_path is not None:
            outputs.append(
                IOItem(
                    label="Queue éditoriale (recommandations writer/canal)",
                    kind="file",
                    detail="shadow — le fondateur déclenche les /draft-* listés",
                    ref=f"data/editorial/{queue_path.name}",
                    count=len(tasks),
                )
            )

        return RunResult(
            status="success",
            output_summary=plan.summary(),
            inputs=inputs,
            outputs=outputs,
        )


__all__ = [
    "EditorialBot",
    "EditorialPlan",
    "assign_tasks",
    "build_editorial_embed",
    "build_queue_doc",
    "find_latest_digest",
    "parse_digest_topics",
    "write_queue",
]
