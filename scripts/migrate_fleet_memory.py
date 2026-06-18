"""Migration ponctuelle : ancienne mémoire de flotte → format pôle/script v2 (S9).

Porte les faits métier encore utiles de l'ancien store ``data/fleet_memory/``
(legacy ``argos_ops.fleet_memory``, 1 dossier par bot) vers la mémoire v2
(:mod:`argos_ops.poles.memory`, ``data/poles/<pole>/scripts/<script>/memory/``).

Mapping : EmailBot → vente/email_bot, LeadEnricher → vente/lead_enricher,
TrendSpotter → veille/trend_spotter. Corps **verbatim** (accents préservés),
``created_at`` et flag ``important`` conservés. Les champs sans équivalent v2
(``confidence``/``status``/``ttl_days``/``archived_at``) sont volontairement
abandonnés — le cycle de vie (TTL, archivage) est désormais piloté par le pôle
Mémoire, plus par le fait.

**Idempotent** : ``write_memory`` dérive l'id du corps ; relancer ne crée pas de
doublon (``created_at`` d'origine préservé). L'ancien store reste en place (il
sert encore au système legacy).

Usage : ``uv run python scripts/migrate_fleet_memory.py``
"""

from __future__ import annotations

import asyncio
import sys
from dataclasses import dataclass
from datetime import datetime

from loguru import logger

from argos_ops.poles.memory import write_memory


@dataclass(frozen=True)
class LegacyFact:
    pole: str
    script: str
    body: str
    kind: str
    tags: tuple[str, ...]
    important: bool
    source: str
    created_at: str  # ISO 8601


# Les 4 faits actifs de l'ancien store, lus verbatim (cf. data/fleet_memory/**).
FACTS: tuple[LegacyFact, ...] = (
    LegacyFact(
        pole="vente",
        script="email_bot",
        body=(
            "Acme Corp (RSSI Marc D.) a demandé un devis pour ~50 scans/mois, "
            "budget annoncé ~8 k€/an. Décision visée avant fin de trimestre."
        ),
        kind="lead-signal",
        tags=("acme-corp", "devis"),
        important=True,  # deal ouvert → protégé de la curation
        source="run#1234 (/run-email-bot)",
        created_at="2026-06-07T14:30:00+00:00",
    ),
    LegacyFact(
        pole="vente",
        script="email_bot",
        body=(
            "Objection récurrente côté PME : l'offre Pro est perçue comme chère sans "
            "option de paiement annualisé. 3 prospects l'ont mentionnée ce mois."
        ),
        kind="objection",
        tags=("pricing", "pme"),
        important=False,
        source="run#1230 (/run-email-bot)",
        created_at="2026-06-06T09:15:00+00:00",
    ),
    LegacyFact(
        pole="vente",
        script="lead_enricher",
        body=(
            "Pattern email dominant chez les ETI cyber FR : prenom.nom@domaine "
            "(score 0.7). Les @gmail/@outlook restent disqualifiés (RGPD perso)."
        ),
        kind="heuristic",
        tags=("icp", "email-pattern"),
        important=True,  # heuristique opérationnelle pérenne
        source="run#1198 (/run-lead-enrich)",
        created_at="2026-06-05T11:00:00+00:00",
    ),
    LegacyFact(
        pole="veille",
        script="trend_spotter",
        body=(
            "Sujet chaud (fenêtre 14j) : exploitation active d'une faille "
            "d'authentification sur des VPN SSL d'entreprise. Fort volume FR."
        ),
        kind="trend",
        tags=("vpn", "cve", "fr"),
        important=False,  # signal éphémère → reste curable à expiration
        source="run#1250 (/run-trend-spot)",
        created_at="2026-06-07T06:00:00+00:00",
    ),
)


async def amain() -> int:
    migrated = 0
    for fact in FACTS:
        record = await write_memory(
            fact.pole,
            fact.script,
            fact.body,
            kind=fact.kind,
            tags=fact.tags,
            important=fact.important,
            source=fact.source,
            created_at=datetime.fromisoformat(fact.created_at),
        )
        migrated += 1
        logger.success(
            f"migre -> {fact.pole}/{fact.script}/{record.id} (important={record.important})"
        )
    logger.info(f"{migrated} fait(s) migré(s) (idempotent — relançable sans doublon).")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(amain()))
