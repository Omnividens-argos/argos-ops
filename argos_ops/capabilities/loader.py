"""Chargement + résolution des capabilities depuis ``data/agent_capabilities.yaml``.

Schéma YAML ::

    capabilities:
      - subject: OutboundBot
        object: EmailBot
        permission: read          # read | write_back
        kind_filter: [lead-signal]  # optionnel — vide = tous les kinds
        tag_filter: [inbound]       # optionnel — ET logique
        enabled: true
        notes: "OutboundBot priorise les leads inbound chauds d'EmailBot"

Fichier absent → liste vide (et ``read`` retombe sur le graphe d'accès :
défaut ALLOW). Une entrée malformée est ignorée (loguée), jamais fatale.
"""

from __future__ import annotations

from pathlib import Path

import yaml
from loguru import logger

from argos_ops.capabilities.models import CapabilityPermission, CapabilityRule
from argos_ops.config import REPO_ROOT
from argos_ops.fleet_memory import GRAPH_WILDCARD

DEFAULT_CAPABILITIES_PATH: Path = REPO_ROOT / "data" / "agent_capabilities.yaml"

_VALID_PERMISSIONS: tuple[CapabilityPermission, ...] = ("read", "write_back")


def _as_str_tuple(value: object) -> tuple[str, ...]:
    if isinstance(value, list):
        return tuple(str(v) for v in value)
    if value is None:
        return ()
    return (str(value),)


def load_capabilities(path: Path = DEFAULT_CAPABILITIES_PATH) -> list[CapabilityRule]:
    """Parse le YAML des capabilities. Entrées malformées ignorées (loguées)."""
    if not path.exists():
        return []
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    entries = raw.get("capabilities", []) if isinstance(raw, dict) else []
    rules: list[CapabilityRule] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        subject = str(entry.get("subject", "")).strip()
        obj = str(entry.get("object", "")).strip()
        permission = str(entry.get("permission", "read")).strip()
        if not subject or not obj or permission not in _VALID_PERMISSIONS:
            logger.warning(f"capabilities: règle ignorée (champs invalides) — {entry!r}")
            continue
        rules.append(
            CapabilityRule(
                subject=subject,
                object=obj,
                permission=permission,  # validé ∈ _VALID_PERMISSIONS ci-dessus
                kind_filter=_as_str_tuple(entry.get("kind_filter")),
                tag_filter=_as_str_tuple(entry.get("tag_filter")),
                enabled=bool(entry.get("enabled", True)),
                notes=(str(entry["notes"]) if entry.get("notes") is not None else None),
            )
        )
    return rules


def effective_read_rules(
    subject: str,
    rules: list[CapabilityRule],
    access_graph: dict[str, list[str]],
) -> dict[str, CapabilityRule | None]:
    """Résout les objets que ``subject`` peut LIRE + la règle de filtre associée.

    Politique (calquée sur la conception P21) :

    1. **Défaut ALLOW depuis le graphe d'accès** : chaque ``object`` que le
       graphe autorise pour ``subject`` est lisible (règle ``None`` = pas de
       filtre kind/tag).
    2. **Filtre explicite** : une règle ``read enabled=true`` restreint la
       lecture d'un object aux kinds/tags déclarés.
    3. **Deny override** : une règle ``read enabled=false`` retire l'object.

    Retourne ``{object_agent: règle_de_filtre_ou_None}``.
    """
    targets = access_graph.get(subject, [])
    allowed: dict[str, CapabilityRule | None] = {}
    if GRAPH_WILDCARD in targets:
        # « * » : tout objet ayant une entrée dans le graphe (sauf soi).
        for other in access_graph:
            if other != subject:
                allowed[other] = None
    else:
        for obj in targets:
            allowed[obj] = None

    for rule in rules:
        if rule.subject != subject or rule.permission != "read":
            continue
        if not rule.enabled:
            allowed.pop(rule.object, None)  # deny override
        else:
            allowed[rule.object] = rule  # filtre explicite (ajoute ou restreint)
    return allowed


def find_write_back_rule(
    subject: str, obj: str, rules: list[CapabilityRule]
) -> CapabilityRule | None:
    """Règle ``write_back enabled=true`` autorisant ``subject`` → ``object``."""
    for rule in rules:
        if (
            rule.permission == "write_back"
            and rule.enabled
            and rule.subject == subject
            and rule.object == obj
        ):
            return rule
    return None


__all__ = [
    "DEFAULT_CAPABILITIES_PATH",
    "effective_read_rules",
    "find_write_back_rule",
    "load_capabilities",
]
