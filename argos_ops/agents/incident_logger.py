"""IncidentLogger — RSSI (P22.E Compliance Sprint 8).

Scaffold un post-mortem d'incident sécurité interne dans
``data/compliance/incidents/<YYYY-MM-DD>-<slug>.md`` à partir d'un titre
+ d'une catégorie (``data_leak`` / ``intrusion`` / ``downtime`` /
``misconfig`` / ``other``).

À la différence des autres bots Compliance qui sont des watchers passifs,
``IncidentLogger`` est un **agent interactif** invoqué via ``/log-incident``.
Le slash command demande au founder de renseigner le titre, la catégorie,
la sévérité, puis Claude appelle :func:`scaffold_incident` qui produit un
fichier markdown template-ready à compléter par un humain.

Politique :
- Pas de push Discord (les incidents internes restent locaux par défaut)
- Le fichier produit est commité ailleurs par le founder, pas par le bot
- Idempotent : re-lancer avec le même slug le même jour réutilise le
  fichier existant

Cf. plan ``docs/ARGOS_OPS_PLAN.md`` Annexe D § 9 Compliance, Sprint 8.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Literal

from loguru import logger

from argos_ops.agents.base import BaseAgent, IOItem, RunResult
from argos_ops.config import REPO_ROOT

IncidentCategory = Literal[
    "data_leak", "intrusion", "downtime", "misconfig", "other"
]
IncidentSeverity = Literal["P0", "P1", "P2", "P3"]

DEFAULT_INCIDENTS_DIR: Path = REPO_ROOT / "data" / "compliance" / "incidents"

VALID_CATEGORIES: frozenset[str] = frozenset(
    {"data_leak", "intrusion", "downtime", "misconfig", "other"}
)
VALID_SEVERITIES: frozenset[str] = frozenset({"P0", "P1", "P2", "P3"})


@dataclass(frozen=True)
class IncidentScaffold:
    """Résultat du scaffold d'un incident."""

    path: Path
    slug: str
    created: bool  # False = fichier existait déjà


# =============================================================================
# Slugify déterministe
# =============================================================================
def slugify(title: str) -> str:
    """Convertit un titre en slug ASCII compatible filesystem."""
    s = title.lower()
    s = re.sub(r"[^\w\s-]", "", s, flags=re.ASCII)
    s = re.sub(r"\s+", "-", s).strip("-")
    return s[:60] or "untitled"


# =============================================================================
# Template post-mortem
# =============================================================================
_TEMPLATE = """---
title: {title}
date: {date}
category: {category}
severity: {severity}
status: open
reporter: {reporter}
---

# Post-mortem — {title}

## Résumé en 1 ligne

> _À compléter : 1 phrase factuelle qui décrit l'incident._

## Chronologie

| Heure (UTC) | Événement |
|-------------|-----------|
| TBD         | Détection |
| TBD         | Mitigation |
| TBD         | Résolution |

## Impact

- Utilisateurs touchés : TBD
- Données touchées : TBD
- Durée totale : TBD
- Notification CNIL requise (>72h, RGPD art. 33) : TBD

## Cause racine

> _À compléter — éviter les « erreur humaine » sans contexte. Décrire
> le défaut système / process qui a permis l'incident._

## Mitigation immédiate

- [ ] TBD

## Actions correctives (court terme)

- [ ] TBD

## Actions préventives (moyen terme)

- [ ] TBD

## Lessons learned

> _Ce qu'on garde de l'incident pour les futures décisions
> (alimente DECISIONS.md si nécessaire)._

---

*Post-mortem créé par IncidentLogger (P22.E). Fichier à compléter
manuellement par le founder, puis commit dans la branche
`chore/incident-{slug}` pour traçabilité.*
"""


def scaffold_incident(
    *,
    title: str,
    category: IncidentCategory,
    severity: IncidentSeverity,
    reporter: str = "founder",
    incidents_dir: Path = DEFAULT_INCIDENTS_DIR,
    today: date | None = None,
) -> IncidentScaffold:
    """Crée le fichier post-mortem si absent. Retourne le scaffold.

    Idempotent : si le fichier ``<YYYY-MM-DD>-<slug>.md`` existe déjà,
    on ne l'écrase pas — on retourne ``created=False``.

    Lève ``ValueError`` si ``category`` ou ``severity`` ne sont pas
    dans les enums canoniques.
    """
    if category not in VALID_CATEGORIES:
        raise ValueError(f"category invalide : {category}")
    if severity not in VALID_SEVERITIES:
        raise ValueError(f"severity invalide : {severity}")

    today = today or datetime.now(UTC).date()
    slug = slugify(title)
    filename = f"{today.isoformat()}-{slug}.md"
    incidents_dir.mkdir(parents=True, exist_ok=True)
    path = incidents_dir / filename
    if path.exists():
        return IncidentScaffold(path=path, slug=slug, created=False)

    body = _TEMPLATE.format(
        title=title,
        date=today.isoformat(),
        category=category,
        severity=severity,
        reporter=reporter,
        slug=slug,
    )
    path.write_text(body, encoding="utf-8")
    return IncidentScaffold(path=path, slug=slug, created=True)


# =============================================================================
# Agent
# =============================================================================
class IncidentLogger(BaseAgent):
    """RSSI — scaffold un post-mortem d'incident depuis ``/log-incident``.

    Mode programmatique uniquement (pas de prompt user) : l'agent
    expose :func:`scaffold_incident` que le slash command appelle après
    avoir collecté les inputs.

    Quand invoqué comme BaseAgent.run() (cron / health-check), il ne
    fait que vérifier que le dossier ``incidents/`` est accessible —
    aucun scaffold automatique.
    """

    name = "IncidentLogger"
    command = "/log-incident"
    breaker_name = None
    ai_act_risk_class = "minimal"

    def __init__(self, *, incidents_dir: Path = DEFAULT_INCIDENTS_DIR) -> None:
        self._incidents_dir = incidents_dir

    async def run(self) -> RunResult:
        """Health check passif — vérifie l'écriture dans ``incidents/``."""
        try:
            self._incidents_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            logger.error(f"IncidentLogger — impossible de créer {self._incidents_dir}: {exc}")
            return RunResult(
                status="failed",
                error=f"mkdir failed: {exc}",
            )
        count = sum(1 for _ in self._incidents_dir.glob("*.md"))
        return RunResult(
            status="success",
            output_summary=f"incidents dir OK ({count} post-mortems archivés)",
            extras={"incidents_count": count},
            inputs=[
                IOItem(
                    label="Post-mortems d'incident archivés",
                    kind="file",
                    detail="health check passif (vérifie l'accès au dossier)",
                    ref="data/compliance/incidents/",
                    count=count,
                )
            ],
        )


__all__ = [
    "DEFAULT_INCIDENTS_DIR",
    "VALID_CATEGORIES",
    "VALID_SEVERITIES",
    "IncidentCategory",
    "IncidentLogger",
    "IncidentScaffold",
    "IncidentSeverity",
    "scaffold_incident",
    "slugify",
]
