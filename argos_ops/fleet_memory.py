"""Mémoire de flotte Argos Ops — socle du Cockpit (LOT 1).

Modèle validé par le fondateur (cf. spec session « Mémoire de flotte ») :

- ``data/fleet_memory/`` = un dossier par bot, clé = ``agent_name`` canonique
  (``EmailBot``), strictement aligné sur :class:`argos_ops.crm.models.AgentRun`
  et :class:`argos_ops.crm.models.AgentConfig` → jointure sans table de mapping.
- **1 fait = 1 fichier** ``<AgentName>/facts/<fact_id>.md`` (frontmatter YAML
  complet + corps markdown), calqué sur la mémoire Claude perso.
- ``<AgentName>/INDEX.md`` = index local (1 ligne / fait), auto-régénéré.
- ``MEMORY.md`` (racine) = index global + **graphe d'accès** « qui lit qui »,
  dans un bloc YAML balisé.

Le « IN » d'un bot = sa propre mémoire + la mémoire des bots qu'il a le droit
de lire (graphe). Garde-fou central : un bot absent du graphe ne voit QUE sa
propre mémoire (cf. :func:`visible_memory`).

Contraintes (D-017, CLAUDE.md) : 100 % fichiers local-first, aucune API tierce,
``loguru`` only, aucune valeur secrète ici (ce sont des faits métier).
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, TypedDict, cast

import yaml
from loguru import logger

from argos_ops.config import REPO_ROOT

FLEET_MEMORY_DIR = REPO_ROOT / "data" / "fleet_memory"
MEMORY_INDEX_FILE = "MEMORY.md"
FACTS_DIRNAME = "facts"
BOT_INDEX_FILE = "INDEX.md"

# Marqueurs du bloc graphe d'accès dans MEMORY.md.
GRAPH_START = "<!-- fleet-access-graph:start -->"
GRAPH_END = "<!-- fleet-access-graph:end -->"
GRAPH_WILDCARD = "*"  # « lit toute la flotte » (orchestrateur / curator).

Confidence = Literal["low", "medium", "high"]
FactStatus = Literal["active", "archived"]

# TTL appliqué par remember() quand un bot n'en précise pas : aucun fait
# auto-extrait n'est éternel par défaut (l'éternel = pinned, décision humaine).
DEFAULT_FACT_TTL_DAYS = 180


class FactDraft(TypedDict, total=False):
    """Fait brut qu'un bot demande à conserver en fin de run.

    Seul ``body`` est requis. Convention : un bot remplit
    ``RunResult.extras["fleet_facts"]`` avec une liste de ``FactDraft`` ;
    :func:`argos_ops.agents.base.run_agent` les conserve via :func:`remember`.
    """

    body: str
    kind: str
    confidence: Confidence
    tags: list[str]
    ttl_days: int | None
    source: str | None
    pinned: bool


_FACT_ID_LEN = 12


def _utcnow() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True)
class Fact:
    """Un fait extrait par un bot — sérialisé dans un fichier markdown.

    ``id`` est dérivé du corps normalisé (cf. :func:`compute_fact_id`) : deux
    appends du même contenu produisent le même ``id`` → écriture idempotente.
    """

    id: str
    bot: str
    kind: str
    body: str
    source: str | None = None
    confidence: Confidence = "medium"
    status: FactStatus = "active"
    ttl_days: int | None = None  # prise MemoryCurator (P20) ; None = pas de TTL.
    created_at: datetime = field(default_factory=_utcnow)
    archived_at: datetime | None = None  # prise MemoryCurator (P20).
    tags: tuple[str, ...] = ()
    pinned: bool = False  # « jugé important » : jamais nettoyé/supprimé par le curator.
    run_id: int | None = None  # provenance : id agent_runs du run qui a extrait ce fait.


@dataclass
class BotMemory:
    """Mémoire complète d'un bot : ses faits, triés du plus récent au plus vieux."""

    bot: str
    facts: list[Fact] = field(default_factory=list)

    @property
    def active_facts(self) -> list[Fact]:
        return [f for f in self.facts if f.status == "active"]


# =============================================================================
# Résolution de chemins
# =============================================================================
def _bot_dir(bot: str, root: Path) -> Path:
    return root / bot


def _facts_dir(bot: str, root: Path) -> Path:
    return _bot_dir(bot, root) / FACTS_DIRNAME


def _fact_path(bot: str, fact_id: str, root: Path) -> Path:
    return _facts_dir(bot, root) / f"{fact_id}.md"


# =============================================================================
# Identité d'un fait (idempotence)
# =============================================================================
def _normalize_body(body: str) -> str:
    """Normalise le corps pour le hash : whitespace écrasé, casse repliée."""
    return " ".join(body.split()).strip().lower()


def compute_fact_id(body: str) -> str:
    """Identifiant stable d'un fait à partir de son corps (sha1 tronqué)."""
    digest = hashlib.sha1(_normalize_body(body).encode("utf-8")).hexdigest()
    return digest[:_FACT_ID_LEN]


# =============================================================================
# (Dé)sérialisation frontmatter — idiome maison (cf. social/publisher.py)
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


def _fact_to_markdown(fact: Fact) -> str:
    fm: dict[str, object] = {
        "id": fact.id,
        "bot": fact.bot,
        "kind": fact.kind,
        "source": fact.source,
        "confidence": fact.confidence,
        "status": fact.status,
        "ttl_days": fact.ttl_days,
        "created_at": fact.created_at.isoformat(),
        "archived_at": fact.archived_at.isoformat() if fact.archived_at else None,
        "tags": list(fact.tags),
        "pinned": fact.pinned,
        "run_id": fact.run_id,
    }
    return _join_frontmatter(fm, fact.body)


def _parse_dt(value: object) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value))


def _fact_from_markdown(content: str, *, bot: str) -> Fact:
    fm, body = _split_frontmatter(content)
    raw_tags = fm.get("tags") or []
    tags = tuple(str(t) for t in raw_tags) if isinstance(raw_tags, list) else ()
    created = _parse_dt(fm.get("created_at")) or _utcnow()
    return Fact(
        id=str(fm.get("id") or compute_fact_id(body)),
        bot=str(fm.get("bot") or bot),
        kind=str(fm.get("kind") or "note"),
        body=body.strip(),
        source=(str(fm["source"]) if fm.get("source") is not None else None),
        confidence=cast(Confidence, fm.get("confidence") or "medium"),
        status=cast(FactStatus, fm.get("status") or "active"),
        ttl_days=(int(cast(int, fm["ttl_days"])) if fm.get("ttl_days") is not None else None),
        created_at=created,
        archived_at=_parse_dt(fm.get("archived_at")),
        tags=tags,
        pinned=bool(fm.get("pinned", False)),
        run_id=(int(cast(int, fm["run_id"])) if fm.get("run_id") is not None else None),
    )


# =============================================================================
# Lecture
# =============================================================================
async def read_memory(
    bot: str,
    *,
    root: Path = FLEET_MEMORY_DIR,
    include_archived: bool = False,
) -> BotMemory:
    """Lit la mémoire propre d'un bot.

    Retourne une :class:`BotMemory` vide si le bot n'a pas encore de dossier
    (cas normal : un bot qui n'a rien extrait). Faits triés du plus récent au
    plus ancien. Les faits ``archived`` sont exclus sauf ``include_archived``.
    """
    facts_dir = _facts_dir(bot, root)
    facts: list[Fact] = []
    if facts_dir.is_dir():
        for path in sorted(facts_dir.glob("*.md")):
            fact = _fact_from_markdown(path.read_text(encoding="utf-8"), bot=bot)
            if fact.status == "archived" and not include_archived:
                continue
            facts.append(fact)
    facts.sort(key=lambda f: f.created_at, reverse=True)
    return BotMemory(bot=bot, facts=facts)


# =============================================================================
# Écriture (idempotente)
# =============================================================================
async def append_fact(
    bot: str,
    body: str,
    *,
    kind: str,
    source: str | None = None,
    confidence: Confidence = "medium",
    tags: tuple[str, ...] = (),
    ttl_days: int | None = None,
    pinned: bool = False,
    created_at: datetime | None = None,
    run_id: int | None = None,
    root: Path = FLEET_MEMORY_DIR,
) -> Fact:
    """Écrit un fait dans la mémoire d'un bot. **Idempotent** par corps.

    Si un fait avec le même ``id`` (= même corps normalisé) existe déjà, il est
    retourné tel quel sans réécriture (no-op). Sinon le fait est créé et
    l'``INDEX.md`` du bot régénéré.
    """
    if not body.strip():
        raise ValueError("append_fact: body vide interdit")

    fact_id = compute_fact_id(body)
    path = _fact_path(bot, fact_id, root)
    if path.exists():
        existing = _fact_from_markdown(path.read_text(encoding="utf-8"), bot=bot)
        logger.debug(f"fleet_memory: fait {bot}/{fact_id} déjà présent — skip (idempotent)")
        return existing

    fact = Fact(
        id=fact_id,
        bot=bot,
        kind=kind,
        body=body.strip(),
        source=source,
        confidence=confidence,
        tags=tags,
        ttl_days=ttl_days,
        pinned=pinned,
        created_at=created_at or _utcnow(),
        run_id=run_id,
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_fact_to_markdown(fact), encoding="utf-8")
    await _regenerate_bot_index(bot, root=root)
    logger.info(f"fleet_memory: nouveau fait {bot}/{fact_id} ({kind})")
    return fact


async def remember(
    bot: str,
    drafts: Iterable[FactDraft],
    *,
    default_source: str | None = None,
    run_id: int | None = None,
    root: Path = FLEET_MEMORY_DIR,
) -> list[Fact]:
    """Conserve une série de faits qu'un bot a décidé de retenir (« se souvenir »).

    Appelée par :func:`argos_ops.agents.base.run_agent` après un run réussi, à
    partir de ``RunResult.extras["fleet_facts"]``. Chaque draft sans ``body``
    non vide est ignoré (logué) sans interrompre les autres. Idempotent par
    corps (cf. :func:`append_fact`) : un même souvenir ne se duplique pas.
    """
    stored: list[Fact] = []
    for draft in drafts:
        body = str(draft.get("body", "")).strip()
        if not body:
            logger.warning(f"fleet_memory.remember: draft sans body ignoré ({bot})")
            continue
        raw_tags = draft.get("tags") or []
        pinned = bool(draft.get("pinned", False))
        # TTL par défaut : un draft qui ne mentionne PAS ttl_days hérite de
        # DEFAULT_FACT_TTL_DAYS (sauf pinned). ttl_days=None explicite reste
        # possible pour un fait volontairement sans expiration.
        if "ttl_days" in draft:
            ttl_days = draft.get("ttl_days")
        else:
            ttl_days = None if pinned else DEFAULT_FACT_TTL_DAYS
        fact = await append_fact(
            bot,
            body,
            kind=str(draft.get("kind", "note")),
            source=draft.get("source") or default_source,
            confidence=draft.get("confidence", "medium"),
            tags=tuple(str(t) for t in raw_tags),
            ttl_days=ttl_days,
            pinned=pinned,
            run_id=run_id,
            root=root,
        )
        stored.append(fact)
    return stored


async def archive_fact(
    bot: str,
    fact_id: str,
    *,
    archived_at: datetime | None = None,
    root: Path = FLEET_MEMORY_DIR,
) -> Fact | None:
    """Archive un fait (soft delete) : ``status=archived`` + ``archived_at``.

    Le fichier reste sur disque (suppression dure réservée à MemoryCurator
    P20). Retourne le fait archivé, ``None`` s'il n'existe pas, ou le fait
    inchangé s'il était déjà archivé (idempotent).
    """
    path = _fact_path(bot, fact_id, root)
    if not path.exists():
        logger.warning(f"fleet_memory: archive impossible — {bot}/{fact_id} introuvable")
        return None
    fact = _fact_from_markdown(path.read_text(encoding="utf-8"), bot=bot)
    if fact.status == "archived":
        return fact
    archived = replace(fact, status="archived", archived_at=archived_at or _utcnow())
    path.write_text(_fact_to_markdown(archived), encoding="utf-8")
    await _regenerate_bot_index(bot, root=root)
    logger.info(f"fleet_memory: fait {bot}/{fact_id} archivé")
    return archived


async def restore_fact(bot: str, fact_id: str, *, root: Path = FLEET_MEMORY_DIR) -> Fact | None:
    """Restaure un fait archivé : ``status=active`` + ``archived_at`` effacé.

    Pendant inverse de :func:`archive_fact` — utilisé par le Memory Hub du
    cockpit (contrôle manuel). Retourne ``None`` si le fait n'existe pas,
    le fait inchangé s'il était déjà actif (idempotent).
    """
    path = _fact_path(bot, fact_id, root)
    if not path.exists():
        logger.warning(f"fleet_memory: restore impossible — {bot}/{fact_id} introuvable")
        return None
    fact = _fact_from_markdown(path.read_text(encoding="utf-8"), bot=bot)
    if fact.status == "active":
        return fact
    restored = replace(fact, status="active", archived_at=None)
    path.write_text(_fact_to_markdown(restored), encoding="utf-8")
    await _regenerate_bot_index(bot, root=root)
    logger.info(f"fleet_memory: fait {bot}/{fact_id} restauré")
    return restored


async def set_pinned(
    bot: str,
    fact_id: str,
    pinned: bool,
    *,
    root: Path = FLEET_MEMORY_DIR,
) -> Fact | None:
    """(Dé)pin un fait. Un fait ``pinned`` n'est jamais nettoyé par MemoryCurator.

    Retourne le fait mis à jour, ``None`` s'il n'existe pas. Idempotent.
    """
    path = _fact_path(bot, fact_id, root)
    if not path.exists():
        logger.warning(f"fleet_memory: pin impossible — {bot}/{fact_id} introuvable")
        return None
    fact = _fact_from_markdown(path.read_text(encoding="utf-8"), bot=bot)
    if fact.pinned == pinned:
        return fact
    updated = replace(fact, pinned=pinned)
    path.write_text(_fact_to_markdown(updated), encoding="utf-8")
    await _regenerate_bot_index(bot, root=root)
    logger.info(f"fleet_memory: fait {bot}/{fact_id} pinned={pinned}")
    return updated


async def delete_fact(bot: str, fact_id: str, *, root: Path = FLEET_MEMORY_DIR) -> bool:
    """Supprime définitivement un fait (hard delete).

    Appelé par MemoryCurator (purge des archivés anciens) et par le Memory Hub
    du cockpit (suppression manuelle assumée par le fondateur). Retourne
    ``True`` si le fichier existait et a été supprimé, ``False`` sinon.
    Régénère l'``INDEX.md`` du bot. Irréversible.
    """
    path = _fact_path(bot, fact_id, root)
    if not path.exists():
        return False
    path.unlink()
    await _regenerate_bot_index(bot, root=root)
    logger.info(f"fleet_memory: fait {bot}/{fact_id} supprimé (hard delete)")
    return True


def list_bots(*, root: Path = FLEET_MEMORY_DIR) -> list[str]:
    """Liste les bots ayant un dossier mémoire sur disque (triés)."""
    return _existing_bots(root)


def _hook(body: str, limit: int = 90) -> str:
    flat = " ".join(body.split())
    return flat if len(flat) <= limit else flat[: limit - 1].rstrip() + "…"


async def _regenerate_bot_index(bot: str, *, root: Path = FLEET_MEMORY_DIR) -> None:
    """Régénère ``<bot>/INDEX.md`` depuis les fichiers de faits actifs."""
    memory = await read_memory(bot, root=root)
    lines = [
        f"# {bot} — index mémoire",
        "",
        f"> {len(memory.active_facts)} fait(s) actif(s) · maj {_utcnow().isoformat()}",
        "",
    ]
    for fact in memory.facts:
        lines.append(
            f"- [`{fact.id}`]({FACTS_DIRNAME}/{fact.id}.md) — {fact.kind} · {_hook(fact.body)}"
        )
    index_path = _bot_dir(bot, root) / BOT_INDEX_FILE
    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


# =============================================================================
# Graphe d'accès
# =============================================================================
def _extract_graph_block(content: str) -> str | None:
    start = content.find(GRAPH_START)
    end = content.find(GRAPH_END)
    if start == -1 or end == -1 or end < start:
        return None
    block = content[start + len(GRAPH_START) : end]
    # Retire les éventuelles barrières de code ```yaml ... ```.
    return re.sub(r"```[a-zA-Z]*", "", block).replace("```", "")


async def load_access_graph(*, root: Path = FLEET_MEMORY_DIR) -> dict[str, list[str]]:
    """Parse le graphe d'accès « qui lit qui » depuis ``MEMORY.md``.

    Retourne ``{bot: [bots dont il peut lire la mémoire]}``. ``"*"`` dans la
    liste signifie « toute la flotte ». Dict vide si le fichier ou le bloc est
    absent.
    """
    index_path = root / MEMORY_INDEX_FILE
    if not index_path.is_file():
        logger.warning(f"fleet_memory: {MEMORY_INDEX_FILE} introuvable — graphe vide")
        return {}
    block = _extract_graph_block(index_path.read_text(encoding="utf-8"))
    if not block:
        logger.warning("fleet_memory: bloc graphe d'accès absent de MEMORY.md")
        return {}
    raw = yaml.safe_load(block) or {}
    if not isinstance(raw, dict):
        return {}
    graph: dict[str, list[str]] = {}
    for bot, targets in raw.items():
        if isinstance(targets, list):
            graph[str(bot)] = [str(t) for t in targets]
        elif targets is not None:
            graph[str(bot)] = [str(targets)]
    return graph


def _existing_bots(root: Path) -> list[str]:
    if not root.is_dir():
        return []
    return sorted(p.name for p in root.iterdir() if p.is_dir())


async def resolve_visible_bots(bot: str, *, root: Path = FLEET_MEMORY_DIR) -> list[str]:
    """Liste des bots dont ``bot`` peut lire la mémoire (lui inclus).

    Garde-fou : un bot absent du graphe ne voit QUE lui-même. ``"*"`` étend à
    toute la flotte présente sur disque.
    """
    graph = await load_access_graph(root=root)
    allowed = {bot}
    for target in graph.get(bot, []):
        if target == GRAPH_WILDCARD:
            allowed.update(_existing_bots(root))
        else:
            allowed.add(target)
    return sorted(allowed)


async def visible_memory(bot: str, *, root: Path = FLEET_MEMORY_DIR) -> dict[str, BotMemory]:
    """Compose le « IN mémoire » d'un bot : sa mémoire + celle qu'il peut lire.

    Clé = nom du bot, valeur = sa :class:`BotMemory`. Respecte strictement le
    graphe d'accès (cf. :func:`resolve_visible_bots`).
    """
    visible = await resolve_visible_bots(bot, root=root)
    return {name: await read_memory(name, root=root) for name in visible}


__all__ = [
    "DEFAULT_FACT_TTL_DAYS",
    "FLEET_MEMORY_DIR",
    "GRAPH_WILDCARD",
    "BotMemory",
    "Confidence",
    "Fact",
    "FactDraft",
    "FactStatus",
    "append_fact",
    "archive_fact",
    "compute_fact_id",
    "delete_fact",
    "list_bots",
    "load_access_graph",
    "read_memory",
    "remember",
    "resolve_visible_bots",
    "restore_fact",
    "set_pinned",
    "visible_memory",
]
