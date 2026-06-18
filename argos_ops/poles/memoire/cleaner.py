"""Exécution **gardée** des suppressions validées (archi v2, S7).

Le pôle Mémoire est le **seul** autorisé à supprimer un fait. ``execute_cleanup``
ne supprime QUE les faits explicitement validés par l'humain (preview cockpit) —
et applique **deux garde-fous indépendants** (« Python tranche »), de sorte
qu'aucun fait ``important`` n'est jamais supprimable même si un client buggé/forcé
en demandait l'id :

1. **Re-lecture live** : chaque cible est relue sur disque (:func:`read_record`).
   Un fait ``important`` (si ``protect_important``) ou pattern-protégé est
   **refusé**, peu importe ce que demandait la liste validée.
2. **Appartenance au plan** : la cible doit figurer dans le ``to_delete`` du
   :class:`~argos_ops.poles.memoire.curation.CurationPlan` recalculé à chaud
   (donc périmée ou stale) ; sinon elle est **refusée** (« non éligible »).

Les deux garanties enferment l'invariant : ``to_delete`` exclut déjà
l'``important`` par construction (cf. ``plan_curation``), ET la re-lecture le
re-refuse — défense en profondeur. Chaque passage est journalisé
(:mod:`argos_ops.poles.memoire.history`).

La **file validée** (``data/poles/memoire/validated/<pole>.yaml``) permet au
script cron ``MemoryCleaner`` de rejouer une validation déposée par le cockpit.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import yaml
from loguru import logger

from argos_ops.poles.config import POLES_DIR
from argos_ops.poles.memoire import history
from argos_ops.poles.memoire.curation import plan_curation
from argos_ops.poles.memoire.history import HistoryItem
from argos_ops.poles.memoire.policy import MEMOIRE_POLE, MemoryPolicy, load_policy
from argos_ops.poles.memory import delete_memory, read_pole_memory, read_record

VALIDATED_DIRNAME = "validated"


@dataclass(frozen=True)
class DeletionTarget:
    """Une cible de suppression validée par l'humain."""

    script: str
    record_id: str


@dataclass(frozen=True)
class CleanupResult:
    """Résultat d'un passage du cleaner sur un pôle.

    ``skipped`` = cibles ni supprimées ni refusées (doublons, déjà absentes,
    disparues en cours de run) ; comptabilité exacte :
    ``n_deleted + n_refused + skipped == requested``.
    """

    pole: str
    requested: int
    deleted: tuple[HistoryItem, ...]
    refused: tuple[HistoryItem, ...]
    skipped: int = 0

    @property
    def n_deleted(self) -> int:
        return len(self.deleted)

    @property
    def n_refused(self) -> int:
        return len(self.refused)


async def execute_cleanup(
    pole: str,
    targets: list[DeletionTarget],
    *,
    policy: MemoryPolicy | None = None,
    actor: str = "cockpit",
    now: datetime | None = None,
    record_history: bool = True,
    poles_root: Path = POLES_DIR,
) -> CleanupResult:
    """Supprime UNIQUEMENT les cibles validées qui passent les deux garde-fous.

    Idempotent : une cible déjà absente est ignorée (ni supprimée, ni refusée).
    Journalise le passage sauf ``record_history=False``.
    """
    pol = policy or load_policy(poles_root=poles_root)
    by_script = await read_pole_memory(pole, poles_root=poles_root)
    plan = plan_curation(by_script, pol, pole, now=now)
    candidate_index = {(c.script, c.record_id): c for c in plan.to_delete}
    # Motif de refus du garde-fou 2 : distinguer « pôle non actif » (curation OFF)
    # du « non éligible » (actif mais ni périmé ni stale) — sinon l'audit ment.
    not_eligible_reason = (
        "non éligible (ni périmé ni stale)" if plan.active else "pôle non actif (curation off)"
    )

    deleted: list[HistoryItem] = []
    refused: list[HistoryItem] = []
    skipped = 0
    # Dédoublonne les cibles tout en préservant l'ordre demandé.
    seen: set[tuple[str, str]] = set()
    for target in targets:
        key = (target.script, target.record_id)
        if key in seen:
            skipped += 1  # doublon
            continue
        seen.add(key)

        # Garde-fou 1 — re-lecture live (état réel, pas le plan).
        live = await read_record(pole, target.script, target.record_id, poles_root=poles_root)
        if live is None:
            skipped += 1  # déjà absent : no-op idempotent
            continue
        if pol.protect_important and live.important:
            refused.append(
                HistoryItem(target.script, target.record_id, live.kind, "important — protégé")
            )
            continue
        if pol.is_pattern_protected(kind=live.kind, tags=live.tags, source=live.source):
            refused.append(
                HistoryItem(target.script, target.record_id, live.kind, "pattern protégé")
            )
            continue

        # Garde-fou 2 — appartenance au plan (périmé / stale uniquement).
        candidate = candidate_index.get(key)
        if candidate is None:
            refused.append(
                HistoryItem(target.script, target.record_id, live.kind, not_eligible_reason)
            )
            continue

        if await delete_memory(pole, target.script, target.record_id, poles_root=poles_root):
            deleted.append(
                HistoryItem(target.script, target.record_id, live.kind, candidate.reason)
            )
        else:
            skipped += 1  # disparu entre la re-lecture et la suppression (course)

    result = CleanupResult(
        pole=pole,
        requested=len(targets),
        deleted=tuple(deleted),
        refused=tuple(refused),
        skipped=skipped,
    )
    if record_history and (deleted or refused):
        history.append_run(
            pole,
            actor=actor,
            deleted=result.deleted,
            refused=result.refused,
            at=now,
            poles_root=poles_root,
        )
    logger.info(
        f"memoire.cleaner : {pole} — {result.n_deleted} supprimé(s), "
        f"{result.n_refused} refusé(s) sur {result.requested} demandé(s)"
    )
    return result


# =============================================================================
# File validée (passerelle cockpit → script cron MemoryCleaner)
# =============================================================================
def _validated_dir(*, poles_root: Path = POLES_DIR) -> Path:
    return poles_root / MEMOIRE_POLE / VALIDATED_DIRNAME


def _validated_path(pole: str, *, poles_root: Path = POLES_DIR) -> Path:
    return _validated_dir(poles_root=poles_root) / f"{pole}.yaml"


def enqueue_validated(
    pole: str, targets: list[DeletionTarget], *, poles_root: Path = POLES_DIR
) -> Path:
    """Dépose une liste validée pour traitement différé par le cleaner cron."""
    path = _validated_path(pole, poles_root=poles_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "pole": pole,
        "targets": [{"script": t.script, "record_id": t.record_id} for t in targets],
    }
    path.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return path


def load_validated_queue(*, poles_root: Path = POLES_DIR) -> dict[str, list[DeletionTarget]]:
    """Lit toutes les files validées en attente : ``{pole: [DeletionTarget, ...]}``."""
    qdir = _validated_dir(poles_root=poles_root)
    if not qdir.exists():
        return {}
    out: dict[str, list[DeletionTarget]] = {}
    for path in sorted(qdir.glob("*.yaml")):
        try:
            raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError as exc:
            logger.warning(f"memoire.cleaner : file validée illisible {path} — {exc}")
            continue
        if not isinstance(raw, dict):
            continue
        pole = str(raw.get("pole") or path.stem)
        rows = raw.get("targets") or []
        targets = [
            DeletionTarget(str(r["script"]), str(r["record_id"]))
            for r in rows
            if isinstance(r, dict) and r.get("script") and r.get("record_id")
        ]
        if targets:
            out[pole] = targets
    return out


def clear_validated_queue(pole: str, *, poles_root: Path = POLES_DIR) -> bool:
    """Retire la file validée d'un pôle (après traitement). ``True`` si présente."""
    path = _validated_path(pole, poles_root=poles_root)
    if not path.exists():
        return False
    path.unlink()
    return True


__all__ = [
    "VALIDATED_DIRNAME",
    "CleanupResult",
    "DeletionTarget",
    "clear_validated_queue",
    "enqueue_validated",
    "execute_cleanup",
    "load_validated_queue",
]
