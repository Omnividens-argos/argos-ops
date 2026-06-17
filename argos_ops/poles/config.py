"""Chargement des ``pole.yaml`` — socle archi v2 (pôle / agent / script).

Un **pôle** est une unité métier (Veille, Marketing, Pub, Vente, Finance,
Direction, Mémoire, SRE). Sa configuration vit dans
``data/poles/<pole>/pole.yaml`` et déclare :

- ``agent``    : le cerveau LLM du pôle (``null`` pour le SRE qui n'a aucun
  agent — uniquement des scripts en cron).
- ``scripts``  : les bras déterministes (fetch / calcul / action) du pôle.
- ``reads_cross_pole`` : les pôles dont l'agent a le droit de lire la mémoire
  (``"*"`` = toute la flotte, pour la Direction / la Mémoire).
- ``front_tools`` : les composants partagés du cockpit que l'onglet du pôle
  affiche (``memory_table`` / ``alert_card`` / ``validation_queue``).

Contraintes (D-017, CLAUDE.md) : 100 % fichiers local-first, aucune API tierce,
``loguru`` only. Le chargement est **défensif** : un ``pole.yaml`` malformé lève
:class:`argos_ops.exceptions.ConfigError` (échouer tôt et fort).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml
from loguru import logger

from argos_ops.config import REPO_ROOT
from argos_ops.exceptions import ConfigError

POLES_DIR = REPO_ROOT / "data" / "poles"
POLE_CONFIG_FILE = "pole.yaml"

# Préfixe des pôles « techniques » (ex. ``_example``) : présents sur disque mais
# exclus de :func:`list_poles` — ils ne comptent pas dans les 8 onglets cockpit.
INTERNAL_POLE_PREFIX = "_"

# « lit toute la flotte » dans ``reads_cross_pole`` (Direction / Mémoire),
# aligné sur le wildcard du graphe d'accès de la mémoire de flotte.
CROSS_POLE_WILDCARD = "*"


@dataclass(frozen=True)
class ScriptSpec:
    """Un bras déterministe déclaré par le pôle.

    ``schedule`` (cron 5 champs) n'est obligatoire que pour les scripts SRE
    lancés en cron pur ; ailleurs il documente la cadence cible.
    """

    id: str
    description: str = ""
    schedule: str | None = None


@dataclass(frozen=True)
class AgentSpec:
    """Le cerveau LLM d'un pôle et sa banque de skills.

    ``trigger`` distingue le déclenchement : ``"cron"`` (cas général, pôles
    1-6) ou ``"script"`` (Mémoire — l'agent est réveillé par un script et non
    par l'orchestrateur).
    """

    name: str
    skills: tuple[str, ...] = ()
    trigger: str = "cron"


@dataclass(frozen=True)
class PoleConfig:
    """Configuration complète d'un pôle, désérialisée depuis ``pole.yaml``."""

    id: str
    name: str
    description: str
    agent: AgentSpec | None
    scripts: tuple[ScriptSpec, ...]
    reads_cross_pole: tuple[str, ...]
    front_tools: tuple[str, ...]

    @property
    def has_agent(self) -> bool:
        return self.agent is not None

    @property
    def reads_all_poles(self) -> bool:
        return CROSS_POLE_WILDCARD in self.reads_cross_pole


# =============================================================================
# Résolution de chemins
# =============================================================================
def pole_dir(pole: str, *, poles_root: Path = POLES_DIR) -> Path:
    return poles_root / pole


def pole_config_path(pole: str, *, poles_root: Path = POLES_DIR) -> Path:
    return pole_dir(pole, poles_root=poles_root) / POLE_CONFIG_FILE


# =============================================================================
# Parsing défensif
# =============================================================================
def _as_str_tuple(value: object, *, field: str, pole: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise ConfigError(
            f"pole.yaml ({pole}) : champ '{field}' doit être une liste, pas {type(value).__name__}"
        )
    return tuple(str(v) for v in value)


def _parse_agent(raw: object, *, pole: str) -> AgentSpec | None:
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise ConfigError(f"pole.yaml ({pole}) : champ 'agent' doit être un mapping ou null")
    name = raw.get("name")
    if not name:
        raise ConfigError(f"pole.yaml ({pole}) : agent.name manquant")
    return AgentSpec(
        name=str(name),
        skills=_as_str_tuple(raw.get("skills"), field="agent.skills", pole=pole),
        trigger=str(raw.get("trigger") or "cron"),
    )


def _parse_scripts(raw: object, *, pole: str) -> tuple[ScriptSpec, ...]:
    if raw is None:
        return ()
    if not isinstance(raw, list):
        raise ConfigError(f"pole.yaml ({pole}) : champ 'scripts' doit être une liste")
    specs: list[ScriptSpec] = []
    for item in raw:
        if not isinstance(item, dict):
            raise ConfigError(f"pole.yaml ({pole}) : chaque script doit être un mapping")
        sid = item.get("id")
        if not sid:
            raise ConfigError(f"pole.yaml ({pole}) : un script n'a pas d''id'")
        schedule = item.get("schedule")
        specs.append(
            ScriptSpec(
                id=str(sid),
                description=str(item.get("description") or ""),
                schedule=str(schedule) if schedule else None,
            )
        )
    return tuple(specs)


def load_pole_config(pole: str, *, poles_root: Path = POLES_DIR) -> PoleConfig:
    """Charge et valide ``data/poles/<pole>/pole.yaml``.

    Lève :class:`ConfigError` si le fichier est absent ou malformé.
    """
    path = pole_config_path(pole, poles_root=poles_root)
    if not path.exists():
        raise ConfigError(f"pole.yaml introuvable pour le pôle '{pole}' ({path})")
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise ConfigError(f"pole.yaml ({pole}) : YAML invalide — {exc}") from exc
    if not isinstance(raw, dict):
        raise ConfigError(f"pole.yaml ({pole}) : racine doit être un mapping")

    pole_id = str(raw.get("id") or pole)
    return PoleConfig(
        id=pole_id,
        name=str(raw.get("name") or pole_id),
        description=str(raw.get("description") or ""),
        agent=_parse_agent(raw.get("agent"), pole=pole_id),
        scripts=_parse_scripts(raw.get("scripts"), pole=pole_id),
        reads_cross_pole=_as_str_tuple(
            raw.get("reads_cross_pole"), field="reads_cross_pole", pole=pole_id
        ),
        front_tools=_as_str_tuple(raw.get("front_tools"), field="front_tools", pole=pole_id),
    )


def list_poles(*, poles_root: Path = POLES_DIR, include_internal: bool = False) -> list[str]:
    """Liste les pôles présents sur disque (un sous-dossier avec ``pole.yaml``).

    Les pôles techniques (préfixe ``_``, ex. ``_example``) sont exclus par
    défaut — ils ne font pas partie des 8 onglets cockpit. Tri alphabétique
    stable pour un affichage déterministe.
    """
    if not poles_root.exists():
        return []
    out: list[str] = []
    for child in sorted(poles_root.iterdir()):
        if not child.is_dir():
            continue
        if not include_internal and child.name.startswith(INTERNAL_POLE_PREFIX):
            continue
        if not (child / POLE_CONFIG_FILE).exists():
            logger.debug(f"list_poles : '{child.name}' ignoré (pas de {POLE_CONFIG_FILE})")
            continue
        out.append(child.name)
    return out


def load_all_poles(
    *, poles_root: Path = POLES_DIR, include_internal: bool = False
) -> list[PoleConfig]:
    """Charge tous les pôles valides (pour l'orchestrateur / le cockpit)."""
    return [
        load_pole_config(p, poles_root=poles_root)
        for p in list_poles(poles_root=poles_root, include_internal=include_internal)
    ]
