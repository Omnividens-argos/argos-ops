"""MemoryCurator — Memory Steward de la flotte (P20, adapté au modèle fichiers).

Le « concierge » de la mémoire de flotte (`data/fleet_memory/`). Empêche le
stockage local de déborder et garde la mémoire rangée, sans jamais perdre ce
qui est important.

Politique déterministe (aucun LLM — D-017) :

- **TTL** : un fait actif dont le ``ttl_days`` est dépassé est **archivé**
  (soft delete, `status=archived`). Cycle de vie en 2 temps = filet de sécurité.
- **Stale** : un fait actif sans TTL, plus vieux que ``stale_active_days``
  (défaut 365 j), est **archivé** lui aussi.
- **Purge** : un fait **déjà archivé** depuis plus de ``purge_archived_days``
  (défaut 90 j) est **supprimé définitivement** (hard delete) — c'est ce qui
  libère réellement le disque.
- **Pinned** : un fait ``pinned: true`` (« jugé important ») n'est **jamais**
  archivé ni supprimé, quel que soit son âge.

Les doublons exacts sont déjà impossibles par construction (l'``id`` d'un fait
= empreinte de son corps, cf. :func:`argos_ops.fleet_memory.compute_fact_id`),
donc la dédup ne porte que sur le contenu identique, garanti au moment de
l'écriture. La dédup sémantique (paraphrases) est hors périmètre (pas
d'embeddings sur la mémoire — D-017).

Anti-spam Discord : silence si rien n'a bougé, embed jaune si des faits ont
été archivés / supprimés (webhook ``DISCORD_WEBHOOK_OPS_LOGS``).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path

from argos_ops import fleet_memory
from argos_ops.agents._watcher_base import color_title, emit_alert_or_silence
from argos_ops.agents.base import BaseAgent, IOItem, RunResult
from argos_ops.fleet_memory import Fact
from argos_ops.notifications.discord import GREEN, YELLOW, Embed, EmbedField

DEFAULT_STALE_ACTIVE_DAYS = 365
DEFAULT_PURGE_ARCHIVED_DAYS = 90


@dataclass(frozen=True)
class CurationReport:
    """Résultat d'un passage du curator — satisfait le ``WatcherReport`` protocol."""

    archived: list[tuple[str, str]]  # (bot, fact_id) archivés ce run
    deleted: list[tuple[str, str]]  # (bot, fact_id) supprimés ce run
    pinned_kept: int  # faits importants protégés
    scanned: int  # total faits inspectés
    should_alert: bool
    alert_color: int
    summary: str = field(compare=False)


# =============================================================================
# Décision (pure, testable sans I/O)
# =============================================================================
def plan_for_bot(
    facts: list[Fact],
    *,
    now: datetime,
    stale_active_days: int | None = DEFAULT_STALE_ACTIVE_DAYS,
    purge_archived_days: int | None = DEFAULT_PURGE_ARCHIVED_DAYS,
) -> tuple[list[str], list[str], int]:
    """Décide quoi archiver / supprimer pour un bot donné.

    Retourne ``(ids_à_archiver, ids_à_supprimer, nb_pinned_protégés)``.
    Un fait ``pinned`` est toujours protégé. Un fait TTL-expiré ou stale est
    archivé (pas supprimé) ; seul un fait déjà archivé depuis longtemps est
    supprimé — cycle de vie en 2 temps.
    """
    to_archive: list[str] = []
    to_delete: list[str] = []
    pinned_kept = 0

    for fact in facts:
        if fact.pinned:
            pinned_kept += 1
            continue

        if fact.status == "active":
            expired = fact.ttl_days is not None and now - fact.created_at >= timedelta(
                days=fact.ttl_days
            )
            stale = (
                fact.ttl_days is None
                and stale_active_days is not None
                and now - fact.created_at >= timedelta(days=stale_active_days)
            )
            if expired or stale:
                to_archive.append(fact.id)

        elif fact.status == "archived":
            if (
                purge_archived_days is not None
                and fact.archived_at is not None
                and now - fact.archived_at >= timedelta(days=purge_archived_days)
            ):
                to_delete.append(fact.id)

    return to_archive, to_delete, pinned_kept


def build_report(
    archived: list[tuple[str, str]],
    deleted: list[tuple[str, str]],
    pinned_kept: int,
    scanned: int,
) -> CurationReport:
    should_alert = bool(archived or deleted)
    summary = (
        f"{len(archived)} archivé(s) · {len(deleted)} supprimé(s) · "
        f"{pinned_kept} important(s) protégé(s) · {scanned} fait(s) inspecté(s)"
    )
    return CurationReport(
        archived=archived,
        deleted=deleted,
        pinned_kept=pinned_kept,
        scanned=scanned,
        should_alert=should_alert,
        alert_color=YELLOW if should_alert else GREEN,
        summary=summary,
    )


def _format_pairs(pairs: list[tuple[str, str]], limit: int = 15) -> str:
    shown = [f"{bot}/{fid}" for bot, fid in pairs[:limit]]
    extra = len(pairs) - limit
    if extra > 0:
        shown.append(f"… +{extra}")
    return ", ".join(shown) or "—"


def build_curator_embed(report: CurationReport, *, now: datetime | None = None) -> Embed:
    now = now or datetime.now(UTC)
    fields: list[EmbedField] = []
    if report.archived:
        fields.append(
            EmbedField(
                name=f"Archivés ({len(report.archived)})",
                value=_format_pairs(report.archived)[:1020],
                inline=False,
            )
        )
    if report.deleted:
        fields.append(
            EmbedField(
                name=f"Supprimés ({len(report.deleted)})",
                value=_format_pairs(report.deleted)[:1020],
                inline=False,
            )
        )
    title_status = color_title(report.alert_color, green=GREEN, yellow=YELLOW, red=YELLOW)
    return Embed(
        title=f"MemoryCurator — {title_status}",
        description=report.summary,
        color=report.alert_color,
        fields=fields,
        footer="Argos Ops • MemoryCurator",
        timestamp=now.isoformat(),
    )


# =============================================================================
# Agent
# =============================================================================
class MemoryCurator(BaseAgent):
    """Memory Steward — nettoie la mémoire de flotte (TTL / stale / purge)."""

    name = "MemoryCurator"
    command = "/run-memory-curator"
    breaker_name = None
    ai_act_risk_class = "minimal"

    def __init__(
        self,
        *,
        root: Path = fleet_memory.FLEET_MEMORY_DIR,
        stale_active_days: int | None = DEFAULT_STALE_ACTIVE_DAYS,
        purge_archived_days: int | None = DEFAULT_PURGE_ARCHIVED_DAYS,
    ) -> None:
        self._root = root
        self._stale_active_days = stale_active_days
        self._purge_archived_days = purge_archived_days

    async def curate(self, *, now: datetime | None = None) -> CurationReport:
        """Applique la politique de curation sur toute la flotte (sans Discord)."""
        now = now or datetime.now(UTC)
        archived: list[tuple[str, str]] = []
        deleted: list[tuple[str, str]] = []
        pinned_kept = 0
        scanned = 0

        for bot in fleet_memory.list_bots(root=self._root):
            mem = await fleet_memory.read_memory(bot, root=self._root, include_archived=True)
            scanned += len(mem.facts)
            to_archive, to_delete, pk = plan_for_bot(
                mem.facts,
                now=now,
                stale_active_days=self._stale_active_days,
                purge_archived_days=self._purge_archived_days,
            )
            pinned_kept += pk
            for fid in to_archive:
                await fleet_memory.archive_fact(bot, fid, archived_at=now, root=self._root)
                archived.append((bot, fid))
            for fid in to_delete:
                if await fleet_memory.delete_fact(bot, fid, root=self._root):
                    deleted.append((bot, fid))

        return build_report(archived, deleted, pinned_kept, scanned)

    async def run(self) -> RunResult:
        report = await self.curate()
        inputs = [
            IOItem(
                label="Mémoire de flotte inspectée",
                kind="memory",
                detail=f"{report.scanned} fait(s) sur tous les bots",
                ref=str(self._root),
                count=report.scanned,
            ),
        ]
        outputs = [
            IOItem(
                label="Faits archivés (TTL / stale)",
                kind="memory",
                detail=_format_pairs(report.archived) if report.archived else None,
                ref=str(self._root),
                count=len(report.archived),
            ),
            IOItem(
                label="Faits supprimés (purge définitive)",
                kind="memory",
                detail=_format_pairs(report.deleted) if report.deleted else None,
                ref=str(self._root),
                count=len(report.deleted),
            ),
            IOItem(
                label="Faits importants protégés (pinned)",
                kind="memory",
                count=report.pinned_kept,
            ),
        ]
        return await emit_alert_or_silence(
            report,
            embed_builder=build_curator_embed,
            agent_name=self.name,
            inputs=inputs,
            outputs=outputs,
        )


__all__ = [
    "DEFAULT_PURGE_ARCHIVED_DAYS",
    "DEFAULT_STALE_ACTIVE_DAYS",
    "CurationReport",
    "MemoryCurator",
    "build_curator_embed",
    "build_report",
    "plan_for_bot",
]
