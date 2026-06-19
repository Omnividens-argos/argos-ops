"""File des suppressions **approuvées** en attente de nettoyage (archi v2).

Trace l'**intention** de l'opérateur : depuis le preview du plan de curation
(``CurationPlan.to_delete``), l'humain approuve une liste de cibles ; cette
liste est persistée dans un sidecar unique
``data/poles/memoire/pending_deletions.yaml`` au format ``{ <pole>:
[{script, record_id}], ... }``. L'approbation n'exécute **rien** — le cleaner
(``execute_cleanup``) reste le seul bras armé ; ``approve`` ne fait
qu'enregistrer ce que l'opérateur pourra ensuite nettoyer.

100 % fichier / déterministe (D-017). Lecture **défensive** : fichier absent /
malformé / ligne incomplète ⇒ ignoré sans jamais lever (contrat « jamais
d'exception qui bloque le cockpit »). Écriture idempotente UTF-8, ordre stable,
même style YAML que la file validée du cleaner.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml
from loguru import logger

from argos_ops.poles.config import POLES_DIR
from argos_ops.poles.memoire.policy import MEMOIRE_POLE

PENDING_FILE = "pending_deletions.yaml"

_HEADER = (
    "# Suppressions APPROUVÉES en attente de nettoyage (pôle 7) — archi v2.\n"
    "# Géré par le cockpit (onglet Mémoire → Plan → Approuver). Map\n"
    "# `pole: [{script, record_id}]`. L'approbation n'exécute RIEN : le cleaner\n"
    "# reste le seul bras armé. Cf. S7.\n"
)


@dataclass(frozen=True)
class PendingDeletion:
    """Une cible de suppression approuvée par l'opérateur (en attente du cleaner)."""

    script: str
    record_id: str


def pending_path(*, poles_root: Path = POLES_DIR) -> Path:
    return poles_root / MEMOIRE_POLE / PENDING_FILE


def _row_to_target(raw: object) -> PendingDeletion | None:
    if not isinstance(raw, dict):
        return None
    script = str(raw.get("script") or "").strip()
    record_id = str(raw.get("record_id") or "").strip()
    if not script or not record_id:
        return None
    return PendingDeletion(script=script, record_id=record_id)


def load_pending(*, poles_root: Path = POLES_DIR) -> dict[str, list[PendingDeletion]]:
    """Lit la file approuvée complète : ``{pole: [PendingDeletion, ...]}``.

    Fichier absent / YAML invalide / structure inattendue ⇒ map vide (jamais
    d'exception). Une entrée de pôle sans cible valide est omise.
    """
    path = pending_path(poles_root=poles_root)
    if not path.exists():
        return {}
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        logger.warning(f"memoire.pending : YAML invalide ({exc}) — file vide")
        return {}
    if not isinstance(raw, dict):
        return {}
    out: dict[str, list[PendingDeletion]] = {}
    for pole, rows in raw.items():
        if not isinstance(rows, list):
            continue
        targets = [t for t in map(_row_to_target, rows) if t is not None]
        if targets:
            out[str(pole)] = targets
    return out


def save_pending(
    pending: dict[str, list[PendingDeletion]], *, poles_root: Path = POLES_DIR
) -> Path:
    """Écrit la file approuvée complète (ordre stable + en-tête commenté, UTF-8)."""
    path = pending_path(poles_root=poles_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    body: dict[str, list[dict[str, str]]] = {
        pole: [{"script": t.script, "record_id": t.record_id} for t in targets]
        for pole, targets in sorted(pending.items())
        if targets
    }
    dumped = yaml.safe_dump(body, sort_keys=False, allow_unicode=True)
    path.write_text(_HEADER + dumped, encoding="utf-8")
    logger.debug(f"memoire.pending : file écrite ({len(body)} pôle(s))")
    return path


def set_pending_for_pole(
    pole: str, targets: list[PendingDeletion], *, poles_root: Path = POLES_DIR
) -> int:
    """Remplace la liste approuvée d'un pôle et persiste. Retourne le nb en attente.

    Idempotent côté cibles (déduplication ``(script, record_id)``, ordre
    d'apparition préservé). Une liste vide retire le pôle de la file.
    """
    current = load_pending(poles_root=poles_root)
    seen: set[tuple[str, str]] = set()
    deduped: list[PendingDeletion] = []
    for t in targets:
        key = (t.script, t.record_id)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(t)
    if deduped:
        current[pole] = deduped
    else:
        current.pop(pole, None)
    save_pending(current, poles_root=poles_root)
    return len(deduped)


__all__ = [
    "PENDING_FILE",
    "PendingDeletion",
    "load_pending",
    "pending_path",
    "save_pending",
    "set_pending_for_pole",
]
