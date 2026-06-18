"""Politique de curation du pôle **Mémoire** (archi v2, S7).

Charge / écrit ``data/poles/memoire/policy.yaml`` : sur quels pôles l'agent
Mémoire est **actif**, le flag ``protect_important`` (jamais toucher un fait
``important``), les **patterns auto-protégés** (kinds / tags / sources jamais
nettoyés même sans flag) et les **bornes de rétention** (TTL par kind, fenêtre
de fraîcheur, nb de versions récentes gardées) qui définissent ce qui est
*périmé* / *stale*.

« Le LLM propose, Python tranche » : la policy est purement déterministe et
fichier (D-017). Chargement **défensif** : fichier absent ou champ malformé ⇒
défauts sûrs (jamais d'exception qui bloquerait le cockpit), et toute valeur
incohérente est ramenée dans des bornes sûres.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from loguru import logger

from argos_ops.poles.config import POLES_DIR

POLICY_FILE = "policy.yaml"
MEMOIRE_POLE = "memoire"

# Défauts de rétention — alignés sur la mémoire de flotte legacy
# (``fleet_memory.DEFAULT_FACT_TTL_DAYS`` = 180).
DEFAULT_TTL_DAYS = 180
DEFAULT_KEEP_RECENT_PER_KIND = 5
DEFAULT_MIN_STALE_DAYS = 30


def _as_str_tuple(value: object) -> tuple[str, ...]:
    if isinstance(value, list):
        return tuple(str(v).strip() for v in value if str(v).strip())
    if value is None:
        return ()
    return (str(value).strip(),) if str(value).strip() else ()


def _as_pos_int(value: object, default: int, *, minimum: int = 0) -> int:
    """Entier ≥ ``minimum`` ; valeur absente / illisible / non finie ⇒ ``default``.

    Défensif : YAML 1.1 parse ``.inf`` / ``-.inf`` / ``.nan`` en floats — ``int()``
    sur un infini lève ``OverflowError`` (pas ``ValueError``), qu'on neutralise ici
    pour ne jamais casser :func:`load_policy` (contrat « jamais d'exception »).
    """
    if not isinstance(value, int | float | str):
        return default
    if isinstance(value, float) and not math.isfinite(value):
        return default  # .inf / -.inf / .nan
    try:
        out = int(value)
    except (TypeError, ValueError, OverflowError):
        return default
    return max(minimum, out)


@dataclass(frozen=True)
class MemoryPolicy:
    """Règles déterministes de curation de la mémoire de flotte (archi v2).

    Un pôle absent de ``active_for`` n'est **jamais** nettoyé. Un fait
    ``important`` (si ``protect_important``) ou matchant un pattern protégé
    n'est **jamais** un candidat à la suppression, quel que soit son âge.
    """

    protect_important: bool = True
    active_for: tuple[str, ...] = ()
    protected_kinds: tuple[str, ...] = ()
    protected_tags: tuple[str, ...] = ()
    protected_sources: tuple[str, ...] = ()
    default_ttl_days: int = DEFAULT_TTL_DAYS
    ttl_by_kind: dict[str, int] = field(default_factory=dict)
    keep_recent_per_kind: int = DEFAULT_KEEP_RECENT_PER_KIND
    min_stale_days: int = DEFAULT_MIN_STALE_DAYS

    def is_active(self, pole: str) -> bool:
        """Le pôle est-il soumis à la curation ?"""
        return pole in self.active_for

    def ttl_for(self, kind: str) -> int:
        """TTL (jours) applicable à un ``kind`` — override par kind sinon défaut."""
        return self.ttl_by_kind.get(kind, self.default_ttl_days)

    def is_pattern_protected(self, *, kind: str, tags: tuple[str, ...], source: str | None) -> bool:
        """Le fait est-il protégé par un **pattern** (hors flag ``important``) ?"""
        if kind in self.protected_kinds:
            return True
        if any(t in self.protected_tags for t in tags):
            return True
        return source is not None and source in self.protected_sources


# =============================================================================
# Résolution de chemins
# =============================================================================
def policy_path(*, poles_root: Path = POLES_DIR) -> Path:
    return poles_root / MEMOIRE_POLE / POLICY_FILE


# =============================================================================
# Chargement
# =============================================================================
def load_policy(*, poles_root: Path = POLES_DIR) -> MemoryPolicy:
    """Charge la policy. Fichier absent / malformé ⇒ policy par défaut sûre.

    Par défaut ``protect_important`` reste ``True`` (jamais déduit faux par
    accident) et ``active_for`` vide (aucun pôle nettoyé tant que rien n'est
    déclaré explicitement) — fail-safe.
    """
    path = policy_path(poles_root=poles_root)
    if not path.exists():
        logger.debug(f"memoire.policy : {path} absent — policy par défaut")
        return MemoryPolicy()
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        logger.warning(f"memoire.policy : YAML invalide ({exc}) — policy par défaut")
        return MemoryPolicy()
    if not isinstance(raw, dict):
        return MemoryPolicy()

    ttl_raw = raw.get("ttl_by_kind")
    ttl_by_kind: dict[str, int] = {}
    if isinstance(ttl_raw, dict):
        for k, v in ttl_raw.items():
            ttl_by_kind[str(k)] = _as_pos_int(v, DEFAULT_TTL_DAYS, minimum=1)

    # Fail-safe : clé ABSENTE *ou* présente mais nulle (``protect_important:`` nu,
    # ``~``, ``null``, valeur commentée) ⇒ True. Seule une valeur explicite non
    # nulle peut désactiver la protection (``protect_important: false``). Sinon
    # ``bool(None)`` désactiverait silencieusement l'invariant via une coquille YAML.
    pi_raw = raw.get("protect_important")
    protect_important = True if pi_raw is None else bool(pi_raw)

    return MemoryPolicy(
        protect_important=protect_important,
        active_for=_as_str_tuple(raw.get("active_for")),
        protected_kinds=_as_str_tuple(raw.get("protected_kinds")),
        protected_tags=_as_str_tuple(raw.get("protected_tags")),
        protected_sources=_as_str_tuple(raw.get("protected_sources")),
        default_ttl_days=_as_pos_int(raw.get("default_ttl_days"), DEFAULT_TTL_DAYS, minimum=1),
        ttl_by_kind=ttl_by_kind,
        keep_recent_per_kind=_as_pos_int(
            raw.get("keep_recent_per_kind"), DEFAULT_KEEP_RECENT_PER_KIND, minimum=0
        ),
        min_stale_days=_as_pos_int(raw.get("min_stale_days"), DEFAULT_MIN_STALE_DAYS, minimum=0),
    )


# =============================================================================
# Écriture (config activation par pôle, depuis le cockpit)
# =============================================================================
_HEADER = (
    "# Politique de la Mémoire (pôle 7) — archi v2. Géré par le cockpit\n"
    "# (onglet Mémoire → Activation). `protect_important: true` = un fait flaggé\n"
    "# `important` n'est JAMAIS supprimable. `active_for` = pôles soumis à la\n"
    "# curation (absent ⇒ jamais nettoyé). Patterns auto-protégés + bornes de\n"
    "# rétention (TTL / fraîcheur) définissent le périmé/stale. Cf. S7.\n"
)


def save_policy(policy: MemoryPolicy, *, poles_root: Path = POLES_DIR) -> None:
    """Écrit la policy sur disque (ordre stable + en-tête commenté, UTF-8)."""
    body: dict[str, object] = {
        "protect_important": policy.protect_important,
        "active_for": list(policy.active_for),
        "protected_kinds": list(policy.protected_kinds),
        "protected_tags": list(policy.protected_tags),
        "protected_sources": list(policy.protected_sources),
        "default_ttl_days": policy.default_ttl_days,
        "ttl_by_kind": dict(policy.ttl_by_kind),
        "keep_recent_per_kind": policy.keep_recent_per_kind,
        "min_stale_days": policy.min_stale_days,
    }
    path = policy_path(poles_root=poles_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    dumped = yaml.safe_dump(body, sort_keys=False, allow_unicode=True)
    path.write_text(_HEADER + dumped, encoding="utf-8")
    logger.debug(f"memoire.policy : écrite ({len(policy.active_for)} pôle(s) actif(s))")


def set_pole_active(pole: str, active: bool, *, poles_root: Path = POLES_DIR) -> MemoryPolicy:
    """(Dé)active la curation d'un pôle et persiste. Idempotent."""
    policy = load_policy(poles_root=poles_root)
    current = set(policy.active_for)
    if active:
        current.add(pole)
    else:
        current.discard(pole)
    updated = MemoryPolicy(
        protect_important=policy.protect_important,
        active_for=tuple(sorted(current)),
        protected_kinds=policy.protected_kinds,
        protected_tags=policy.protected_tags,
        protected_sources=policy.protected_sources,
        default_ttl_days=policy.default_ttl_days,
        ttl_by_kind=policy.ttl_by_kind,
        keep_recent_per_kind=policy.keep_recent_per_kind,
        min_stale_days=policy.min_stale_days,
    )
    save_policy(updated, poles_root=poles_root)
    return updated


__all__ = [
    "DEFAULT_KEEP_RECENT_PER_KIND",
    "DEFAULT_MIN_STALE_DAYS",
    "DEFAULT_TTL_DAYS",
    "MEMOIRE_POLE",
    "MemoryPolicy",
    "load_policy",
    "policy_path",
    "save_policy",
    "set_pole_active",
]
