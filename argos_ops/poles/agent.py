"""``BaseAgent`` — le cerveau LLM d'un pôle (socle archi v2).

Un **agent** (1 par pôle 1-6 ; Mémoire = agent déclenché par script ; le SRE
n'en a aucun) :

1. **lit sa mémoire** = celle de tous les scripts de son pôle, **plus** la
   mémoire des pôles déclarés dans ``reads_cross_pole`` de son ``pole.yaml``
   (mécanisme de lecture cross-pôle, ``"*"`` = toute la flotte) ;
2. **agit** : décide / rédige / répond / publie, via sa banque de skills.

Garde-fou central (calqué sur le graphe d'accès de la mémoire de flotte) : un
agent ne lit QUE les pôles listés dans son ``pole.yaml``. Le « LLM propose,
Python tranche » reste la règle — ici le socle ne fait que **fournir le
contexte** ; la décision vit dans :meth:`act` de chaque sous-classe.

``act`` est abstraite et n'appelle pas le cerveau elle-même : sous D-017 c'est
Claude Code (CLI ``claude -p``, flag ``OPS_BRAIN_ENABLED``) qui joue ce rôle,
avec fallback heuristique obligatoire — branché par chaque pôle.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from loguru import logger

from argos_ops.poles import memory
from argos_ops.poles.config import (
    CROSS_POLE_WILDCARD,
    POLES_DIR,
    list_poles,
    load_pole_config,
)
from argos_ops.poles.memory import MemoryRecord

AgentStatus = Literal["success", "failed", "skipped"]


@dataclass
class AgentContext:
    """Tout ce qu'un agent « voit » au début de son tour.

    - ``own`` : ``{script: [MemoryRecord]}`` du propre pôle de l'agent.
    - ``cross_pole`` : ``{pole: {script: [MemoryRecord]}}`` des pôles déclarés
      lisibles (``reads_cross_pole``).
    - ``skills`` : la banque de skills déclarée dans ``pole.yaml``.
    """

    pole: str
    own: dict[str, list[MemoryRecord]] = field(default_factory=dict)
    cross_pole: dict[str, dict[str, list[MemoryRecord]]] = field(default_factory=dict)
    skills: tuple[str, ...] = ()

    def all_records(self) -> list[MemoryRecord]:
        """Tous les faits visibles (propre + cross-pôle), du plus récent au plus vieux."""
        flat: list[MemoryRecord] = []
        for records in self.own.values():
            flat.extend(records)
        for by_script in self.cross_pole.values():
            for records in by_script.values():
                flat.extend(records)
        flat.sort(key=lambda r: r.created_at, reverse=True)
        return flat

    def important(self) -> list[MemoryRecord]:
        """Les seuls faits protégés (``important=True``) parmi tout le visible."""
        return [r for r in self.all_records() if r.important]

    def is_empty(self) -> bool:
        return not self.own and not self.cross_pole


@dataclass
class AgentResult:
    """Résultat d'un tour d'agent : ce qu'il a décidé / produit."""

    status: AgentStatus
    summary: str | None = None
    error: str | None = None
    actions: list[str] = field(default_factory=list)


class BaseAgent(ABC):
    """Tout agent de pôle hérite de cette classe.

    Les sous-classes déclarent ``pole`` et ``name``, implémentent :meth:`act`.
    Le socle fournit :meth:`load_context` (lecture mémoire propre + cross-pôle
    autorisée) et :meth:`run` (charge le contexte → ``act``).
    """

    pole: str  # ex. "veille"
    name: str  # ex. "VeilleAgent"

    def __init__(self, *, poles_root: Path = POLES_DIR) -> None:
        self.poles_root = poles_root

    async def load_context(self) -> AgentContext:
        """Construit le contexte de l'agent à partir du disque.

        Lit la mémoire de son pôle, puis celle des pôles listés dans
        ``reads_cross_pole``. ``"*"`` ⇒ tous les autres pôles. Un pôle déclaré
        mais sans mémoire est simplement absent du contexte (best-effort).
        """
        config = load_pole_config(self.pole, poles_root=self.poles_root)
        own = await memory.read_pole_memory(self.pole, poles_root=self.poles_root)

        targets = self._resolve_cross_pole_targets(config.reads_cross_pole)
        cross: dict[str, dict[str, list[MemoryRecord]]] = {}
        for other in targets:
            other_mem = await memory.read_pole_memory(other, poles_root=self.poles_root)
            if other_mem:
                cross[other] = other_mem

        skills = config.agent.skills if config.agent else ()
        logger.debug(
            f"Agent {self.name} — contexte : {len(own)} script(s) propre(s), "
            f"{len(cross)} pôle(s) cross lu(s)"
        )
        return AgentContext(pole=self.pole, own=own, cross_pole=cross, skills=skills)

    def _resolve_cross_pole_targets(self, reads_cross_pole: tuple[str, ...]) -> list[str]:
        """Résout la liste des pôles à lire (gère le wildcard ``"*"``)."""
        if CROSS_POLE_WILDCARD in reads_cross_pole:
            return [p for p in list_poles(poles_root=self.poles_root) if p != self.pole]
        # Dédup en préservant l'ordre déclaré, et jamais soi-même.
        seen: set[str] = set()
        targets: list[str] = []
        for p in reads_cross_pole:
            if p == self.pole or p in seen:
                continue
            seen.add(p)
            targets.append(p)
        return targets

    @abstractmethod
    async def act(self, context: AgentContext) -> AgentResult:
        """Décide / rédige / agit à partir du contexte. Implémenté par le pôle."""

    async def run(self) -> AgentResult:
        """Charge le contexte (mémoire propre + cross-pôle) puis appelle ``act``."""
        logger.info(f"Agent {self.name} ({self.pole}) — start")
        context = await self.load_context()
        result = await self.act(context)
        logger.info(
            f"Agent {self.name} ({self.pole}) — {result.status} ({len(result.actions)} action(s))"
        )
        return result
