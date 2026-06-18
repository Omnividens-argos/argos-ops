"""Primitives mémoire d'un script — socle archi v2.

Chaque **script** (bras déterministe) possède sa propre mémoire fichier sous
``data/poles/<pole>/scripts/<script>/memory/`` : **1 fait = 1 fichier**
``<id>.md`` (frontmatter YAML + corps markdown), calqué sur la mémoire de
flotte existante (:mod:`argos_ops.fleet_memory`).

- ``id`` est dérivé du corps normalisé → écriture **idempotente** (deux écritures
  du même contenu ⇒ même fichier ; ``created_at`` est préservé, jamais réécrit).
- ``important`` est le flag **protégeable** : un fait important n'est jamais
  archivé/supprimé par l'agent Mémoire (pôle 7). :func:`write_memory` ne
  *déclasse* jamais un fait déjà important (anti-régression).

L'agent d'un pôle lit cette mémoire (la sienne + celle des pôles déclarés dans
``reads_cross_pole``) — cf. :mod:`argos_ops.poles.agent`.

Contraintes (D-017) : 100 % fichiers local-first, aucune API tierce, aucune
valeur secrète ici (ce sont des faits métier), ``loguru`` only.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import yaml
from loguru import logger

from argos_ops.poles.config import POLES_DIR

MEMORY_DIRNAME = "memory"
SCRIPTS_DIRNAME = "scripts"
_RECORD_ID_LEN = 12


def _utcnow() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True)
class MemoryRecord:
    """Un fait écrit par un script — sérialisé dans un fichier markdown.

    ``id`` est stable (hash du corps) ; ``important`` protège le fait de la
    curation. ``created_at`` reflète la **première** écriture (idempotence).
    """

    id: str
    pole: str
    script: str
    kind: str
    body: str
    important: bool = False
    source: str | None = None
    tags: tuple[str, ...] = ()
    created_at: datetime = field(default_factory=_utcnow)


# =============================================================================
# Résolution de chemins
# =============================================================================
def script_memory_dir(pole: str, script: str, *, poles_root: Path = POLES_DIR) -> Path:
    return poles_root / pole / SCRIPTS_DIRNAME / script / MEMORY_DIRNAME


def _record_path(pole: str, script: str, record_id: str, *, poles_root: Path) -> Path:
    return script_memory_dir(pole, script, poles_root=poles_root) / f"{record_id}.md"


# =============================================================================
# Identité (idempotence)
# =============================================================================
def _normalize_body(body: str) -> str:
    return " ".join(body.split()).strip().lower()


def compute_record_id(body: str) -> str:
    """Identifiant stable d'un fait à partir de son corps (sha1 tronqué)."""
    digest = hashlib.sha1(_normalize_body(body).encode("utf-8")).hexdigest()
    return digest[:_RECORD_ID_LEN]


# =============================================================================
# (Dé)sérialisation frontmatter — idiome maison (cf. fleet_memory.py)
# =============================================================================
def _split_frontmatter(content: str) -> tuple[dict[str, object], str]:
    if not content.startswith("---\n"):
        return {}, content
    end = content.find("\n---", 4)
    if end == -1:
        return {}, content
    fm = yaml.safe_load(content[4:end]) or {}
    body = content[end + 5 :]
    return (fm if isinstance(fm, dict) else {}), body


def _join_frontmatter(fm: dict[str, object], body: str) -> str:
    front = yaml.safe_dump(fm, sort_keys=False, allow_unicode=True)
    return f"---\n{front}---\n\n{body.strip()}\n"


def _record_to_markdown(record: MemoryRecord) -> str:
    fm: dict[str, object] = {
        "id": record.id,
        "pole": record.pole,
        "script": record.script,
        "kind": record.kind,
        "important": record.important,
        "source": record.source,
        "created_at": record.created_at.isoformat(),
        "tags": list(record.tags),
    }
    return _join_frontmatter(fm, record.body)


def _parse_dt(value: object) -> datetime | None:
    if value is None:
        return None
    dt = value if isinstance(value, datetime) else datetime.fromisoformat(str(value))
    # Normalise en aware/UTC : un ``created_at`` saisi sans fuseau (ou une date nue
    # ``YYYY-MM-DD``) donnerait un datetime naïf, et le tri mémoire (récent →
    # vieux) mélangeant naïf et aware lève un TypeError — fatal pour la lecture
    # transversale de la Direction (un seul fait mal saisi tuerait tout le snapshot).
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=UTC)


def _record_from_markdown(content: str, *, pole: str, script: str) -> MemoryRecord:
    fm, body = _split_frontmatter(content)
    raw_tags = fm.get("tags") or []
    tags = tuple(str(t) for t in raw_tags) if isinstance(raw_tags, list) else ()
    created = _parse_dt(fm.get("created_at")) or _utcnow()
    return MemoryRecord(
        id=str(fm.get("id") or compute_record_id(body)),
        pole=str(fm.get("pole") or pole),
        script=str(fm.get("script") or script),
        kind=str(fm.get("kind") or "note"),
        body=body.strip(),
        important=bool(fm.get("important", False)),
        source=(str(fm["source"]) if fm.get("source") is not None else None),
        tags=tags,
        created_at=created,
    )


# =============================================================================
# Primitives : write / read / flag
# =============================================================================
async def write_memory(
    pole: str,
    script: str,
    body: str,
    *,
    kind: str = "note",
    tags: tuple[str, ...] = (),
    important: bool = False,
    source: str | None = None,
    created_at: datetime | None = None,
    poles_root: Path = POLES_DIR,
) -> MemoryRecord:
    """Écrit (ou met à jour) un fait dans la mémoire d'un script. Idempotent.

    Si un fait de même corps existe déjà : ``created_at`` est préservé et le
    flag ``important`` n'est **jamais** déclassé (``important or existing``).
    """
    if not body.strip():
        raise ValueError("write_memory : corps vide interdit")
    record_id = compute_record_id(body)
    path = _record_path(pole, script, record_id, poles_root=poles_root)

    existing_created = created_at
    existing_important = important
    if path.exists():
        prev = _record_from_markdown(path.read_text(encoding="utf-8"), pole=pole, script=script)
        existing_created = existing_created or prev.created_at
        existing_important = important or prev.important

    record = MemoryRecord(
        id=record_id,
        pole=pole,
        script=script,
        kind=kind,
        body=body.strip(),
        important=existing_important,
        source=source,
        tags=tags,
        created_at=existing_created or _utcnow(),
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_record_to_markdown(record), encoding="utf-8")
    logger.debug(f"memory write — {pole}/{script}/{record_id} (important={record.important})")
    return record


async def read_memory(
    pole: str, script: str, *, poles_root: Path = POLES_DIR
) -> list[MemoryRecord]:
    """Lit tous les faits d'un script, du plus récent au plus ancien.

    Best-effort : un fichier illisible est logué et sauté (jamais d'exception
    qui casserait la lecture mémoire d'un agent).
    """
    mem_dir = script_memory_dir(pole, script, poles_root=poles_root)
    if not mem_dir.exists():
        return []
    records: list[MemoryRecord] = []
    for path in mem_dir.glob("*.md"):
        try:
            records.append(
                _record_from_markdown(path.read_text(encoding="utf-8"), pole=pole, script=script)
            )
        except Exception as exc:  # best-effort, comme fleet_memory
            logger.warning(f"memory read — fichier illisible {path} : {type(exc).__name__}: {exc}")
    # Tiebreaker ``id`` : ordre TOTAL et déterministe quand plusieurs faits
    # partagent le même ``created_at`` (sinon l'ordre du glob filesystem fuiterait
    # dans le tri — non reproductible d'une machine à l'autre).
    records.sort(key=lambda r: (r.created_at, r.id), reverse=True)
    return records


async def flag_important(
    pole: str,
    script: str,
    record_id: str,
    *,
    important: bool = True,
    poles_root: Path = POLES_DIR,
) -> MemoryRecord | None:
    """Bascule le flag ``important`` d'un fait. Renvoie ``None`` si absent."""
    path = _record_path(pole, script, record_id, poles_root=poles_root)
    if not path.exists():
        logger.warning(f"flag_important — fait introuvable {pole}/{script}/{record_id}")
        return None
    prev = _record_from_markdown(path.read_text(encoding="utf-8"), pole=pole, script=script)
    updated = MemoryRecord(
        id=prev.id,
        pole=prev.pole,
        script=prev.script,
        kind=prev.kind,
        body=prev.body,
        important=important,
        source=prev.source,
        tags=prev.tags,
        created_at=prev.created_at,
    )
    path.write_text(_record_to_markdown(updated), encoding="utf-8")
    logger.debug(f"flag_important — {pole}/{script}/{record_id} → {important}")
    return updated


async def read_record(
    pole: str, script: str, record_id: str, *, poles_root: Path = POLES_DIR
) -> MemoryRecord | None:
    """Relit un fait précis (par id). ``None`` s'il n'existe pas ou est illisible.

    Brique de **re-vérification** du pôle Mémoire : avant toute suppression, le
    cleaner relit le fait sur disque pour décider à partir de l'état réel (et non
    d'un plan possiblement périmé), garde-fou de l'invariant « un fait
    ``important`` n'est jamais supprimable ».
    """
    path = _record_path(pole, script, record_id, poles_root=poles_root)
    if not path.exists():
        return None
    try:
        return _record_from_markdown(path.read_text(encoding="utf-8"), pole=pole, script=script)
    except Exception as exc:  # best-effort, comme read_memory
        logger.warning(f"read_record — fichier illisible {path} : {type(exc).__name__}: {exc}")
        return None


async def delete_memory(
    pole: str, script: str, record_id: str, *, poles_root: Path = POLES_DIR
) -> bool:
    """Supprime **définitivement** un fait (hard delete). Irréversible.

    Renvoie ``True`` si le fichier existait et a été supprimé, ``False`` sinon.
    Primitive **bas niveau, sans garde-fou** : la protection de l'``important``
    vit dans le pôle Mémoire (seul autorisé à supprimer — cf.
    :mod:`argos_ops.poles.memoire.cleaner`), qui re-vérifie chaque fait via
    :func:`read_record` avant d'appeler cette fonction. Ne JAMAIS appeler
    ailleurs sans cette re-vérification.
    """
    path = _record_path(pole, script, record_id, poles_root=poles_root)
    if not path.exists():
        return False
    path.unlink()
    logger.info(f"memory delete — {pole}/{script}/{record_id} (hard delete)")
    return True


def list_script_memories(pole: str, *, poles_root: Path = POLES_DIR) -> list[str]:
    """Noms des scripts du pôle qui ont un dossier ``memory/`` non vide-de-dossier."""
    scripts_dir = poles_root / pole / SCRIPTS_DIRNAME
    if not scripts_dir.exists():
        return []
    out: list[str] = []
    for child in sorted(scripts_dir.iterdir()):
        if child.is_dir() and (child / MEMORY_DIRNAME).exists():
            out.append(child.name)
    return out


async def read_pole_memory(
    pole: str, *, poles_root: Path = POLES_DIR
) -> dict[str, list[MemoryRecord]]:
    """Lit la mémoire de **tous** les scripts d'un pôle.

    Renvoie ``{script_name: [MemoryRecord, ...]}`` (vide si le pôle n'a aucune
    mémoire). C'est la brique de lecture réutilisée pour la mémoire propre d'un
    agent **et** pour les lectures cross-pôle.
    """
    out: dict[str, list[MemoryRecord]] = {}
    for script in list_script_memories(pole, poles_root=poles_root):
        records = await read_memory(pole, script, poles_root=poles_root)
        if records:
            out[script] = records
    return out
