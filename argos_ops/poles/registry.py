"""Registre de la flotte — le **câblage** des 8 pôles (archi v2, S9).

Source unique reliant chaque pôle à ses **bras déterministes** (scripts) et à son
**cerveau** (agent), pour que l'orchestrateur de flotte
(:mod:`argos_ops.poles.fleet`) puisse planifier / lancer n'importe quel script et
réveiller n'importe quel agent — sans connaître les détails internes de chaque pôle.

100 % statique : importer ce module ne touche ni disque ni réseau (uniquement des
imports de classes). Les pôles sans cerveau (SRE) ont ``None`` comme agent.

Invariant vérifié par :func:`validate_registry` (et le test de câblage S9) : ce
registre Python et les ``pole.yaml`` déclarent **exactement** les mêmes scripts —
toute dérive (script déclaré mais non enregistré, ou l'inverse) est une erreur de
câblage.
"""

from __future__ import annotations

from argos_ops.poles.agent import BaseAgent
from argos_ops.poles.base import BaseScript
from argos_ops.poles.config import POLES_DIR, list_poles, load_pole_config
from argos_ops.poles.direction.agent import DirectionAgent
from argos_ops.poles.direction.scripts import DIRECTION_SCRIPTS
from argos_ops.poles.finance.agent import FinanceAgent
from argos_ops.poles.finance.scripts import FINANCE_SCRIPTS
from argos_ops.poles.marketing.agent import MarketingAgent
from argos_ops.poles.marketing.scripts import MARKETING_SCRIPTS
from argos_ops.poles.memoire.agent import MemoireAgent
from argos_ops.poles.memoire.scripts import MEMOIRE_SCRIPTS
from argos_ops.poles.pub.agent import PubAgent
from argos_ops.poles.pub.scripts import PUB_SCRIPTS
from argos_ops.poles.sre.scripts import SRE_SCRIPTS
from argos_ops.poles.veille.agent import VeilleAgent
from argos_ops.poles.veille.scripts import VEILLE_SCRIPTS
from argos_ops.poles.vente.agent import VenteAgent
from argos_ops.poles.vente.scripts import VENTE_SCRIPTS

# Ordre canonique de la flotte (= ordre métier amont → aval → transversal → SRE).
POLE_ORDER: tuple[str, ...] = (
    "veille",
    "marketing",
    "pub",
    "vente",
    "finance",
    "direction",
    "memoire",
    "sre",
)

# pole id -> bras déterministes (ordre cron canonique = pole.yaml).
POLE_SCRIPTS: dict[str, tuple[type[BaseScript], ...]] = {
    "veille": VEILLE_SCRIPTS,
    "marketing": MARKETING_SCRIPTS,
    "pub": PUB_SCRIPTS,
    "vente": VENTE_SCRIPTS,
    "finance": FINANCE_SCRIPTS,
    "direction": DIRECTION_SCRIPTS,
    "memoire": MEMOIRE_SCRIPTS,
    "sre": SRE_SCRIPTS,
}

# pole id -> cerveau LLM (``None`` = pôle sans agent, c.-à-d. SRE / Meta-Ops).
POLE_AGENTS: dict[str, type[BaseAgent] | None] = {
    "veille": VeilleAgent,
    "marketing": MarketingAgent,
    "pub": PubAgent,
    "vente": VenteAgent,
    "finance": FinanceAgent,
    "direction": DirectionAgent,
    "memoire": MemoireAgent,
    "sre": None,
}


# =============================================================================
# Accès
# =============================================================================
def script_registry(pole: str) -> dict[str, type[BaseScript]]:
    """``{script_name: classe}`` des bras d'un pôle (``{}`` si pôle inconnu)."""
    return {cls.name: cls for cls in POLE_SCRIPTS.get(pole, ())}


def script_class(pole: str, script: str) -> type[BaseScript] | None:
    """Classe exécutable d'un script (``None`` si pôle/script inconnu)."""
    return script_registry(pole).get(script)


def agent_class(pole: str) -> type[BaseAgent] | None:
    """Classe du cerveau d'un pôle (``None`` si le pôle n'a pas d'agent)."""
    return POLE_AGENTS.get(pole)


def has_agent(pole: str) -> bool:
    return POLE_AGENTS.get(pole) is not None


def all_script_ids() -> list[tuple[str, str]]:
    """Tous les couples ``(pole, script)`` de la flotte, ordre canonique."""
    out: list[tuple[str, str]] = []
    for pole in POLE_ORDER:
        for cls in POLE_SCRIPTS.get(pole, ()):
            out.append((pole, cls.name))
    return out


# =============================================================================
# Vérification du câblage (registre Python ⇄ pole.yaml)
# =============================================================================
def validate_registry(*, poles_root: object = POLES_DIR) -> list[str]:
    """Croise le registre avec les ``pole.yaml`` : renvoie la liste des écarts.

    Liste vide ⇒ câblage cohérent. Détecte : pôle sur disque absent du registre
    (et l'inverse), script déclaré dans ``pole.yaml`` mais non enregistré (et
    l'inverse), nom de script dupliqué dans un pôle (collision qui s'effondrerait
    silencieusement dans :func:`script_registry`), et incohérence ``cls.pole`` vs
    pôle d'enregistrement.
    """
    from collections import Counter
    from pathlib import Path

    root = poles_root if isinstance(poles_root, Path) else Path(str(poles_root))
    problems: list[str] = []

    disk_poles = set(list_poles(poles_root=root))
    registry_poles = set(POLE_SCRIPTS)
    for missing in sorted(disk_poles - registry_poles):
        problems.append(f"pôle '{missing}' présent sur disque mais absent du registre")
    for extra in sorted(registry_poles - disk_poles):
        problems.append(f"pôle '{extra}' dans le registre mais absent du disque")

    for pole in sorted(disk_poles & registry_poles):
        declared = {spec.id for spec in load_pole_config(pole, poles_root=root).scripts}
        registered = set(script_registry(pole))
        for missing in sorted(declared - registered):
            problems.append(f"{pole}: script '{missing}' déclaré (pole.yaml) mais non enregistré")
        for extra in sorted(registered - declared):
            problems.append(f"{pole}: script '{extra}' enregistré mais absent de pole.yaml")
        # Noms dupliqués dans la tuple du pôle : script_registry les écraserait
        # silencieusement (clé = name) — on les détecte sur la tuple, pas le dict.
        dups = sorted(
            n for n, c in Counter(cls.name for cls in POLE_SCRIPTS[pole]).items() if c > 1
        )
        if dups:
            problems.append(f"{pole}: nom(s) de script dupliqué(s) dans le registre : {dups}")
        for cls in POLE_SCRIPTS[pole]:
            if cls.pole != pole:
                problems.append(
                    f"{pole}: {cls.__name__}.pole='{cls.pole}' ≠ pôle d'enregistrement '{pole}'"
                )

    return problems


__all__ = [
    "POLE_AGENTS",
    "POLE_ORDER",
    "POLE_SCRIPTS",
    "agent_class",
    "all_script_ids",
    "has_agent",
    "script_class",
    "script_registry",
    "validate_registry",
]
