"""Audit du **câblage inter-pôles** — CapabilityRouter v2 (archi v2, S7).

En archi v2, le « qui lit la mémoire de qui » n'est plus le graphe d'accès
``MEMORY.md`` (legacy fleet) mais le champ ``reads_cross_pole`` de chaque
``pole.yaml`` (``"*"`` = toute la flotte, pour Direction / Mémoire). Ce module
en fait l'audit **read-only**, miroir v2 du ``CapabilityRouter`` P21 :

- **orphan** : un pôle déclare lire un pôle qui n'existe pas (typo / pôle retiré).
- **self_reference** : un pôle se liste lui-même (redondant — dédupliqué par le
  socle, mais signalé).
- **empty_target** : un câblage pointe un pôle dont la mémoire est vide
  (câblage à vide — info).
- **unread_producer** : un pôle qui **produit** de la mémoire mais que
  **personne** ne lit (mémoire en cul-de-sac — warning).

Silence (``should_alert=False``) si le câblage est sain (aucun warning).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from argos_ops.poles.config import POLES_DIR, PoleConfig, load_all_poles
from argos_ops.poles.memory import read_pole_memory

AnomalyKind = Literal["orphan", "self_reference", "empty_target", "unread_producer"]
Severity = Literal["info", "warning"]


@dataclass(frozen=True)
class WiringEdge:
    """Une arête « ``source`` lit la mémoire de ``target`` »."""

    source: str
    target: str
    via_wildcard: bool
    target_facts: int


@dataclass(frozen=True)
class WiringAnomaly:
    kind: AnomalyKind
    pole: str
    detail: str
    severity: Severity


@dataclass(frozen=True)
class WiringAudit:
    """Résultat de l'audit du câblage (read-only)."""

    generated_at: datetime
    poles: tuple[str, ...]
    edges: tuple[WiringEdge, ...]
    anomalies: tuple[WiringAnomaly, ...]
    should_alert: bool
    summary: str

    @property
    def n_edges(self) -> int:
        return len(self.edges)

    @property
    def n_anomalies(self) -> int:
        return len(self.anomalies)

    @property
    def n_warning(self) -> int:
        return sum(1 for a in self.anomalies if a.severity == "warning")


def _resolve_targets(
    config: PoleConfig, all_ids: set[str]
) -> tuple[list[tuple[str, bool]], list[WiringAnomaly]]:
    """Résout les cibles lues par un pôle + ses anomalies de déclaration.

    Retourne ``([(target, via_wildcard), ...], [anomalies])``. Le wildcard
    s'étend à tous les autres pôles existants ; une cible explicite inconnue
    devient une anomalie ``orphan``, une auto-référence une anomalie
    ``self_reference`` (toutes deux sans arête).
    """
    if config.agent is None:
        return [], []  # pôle sans cerveau (SRE) : ne lit rien par conception.
    if config.reads_all_poles:
        return [(other, True) for other in sorted(all_ids) if other != config.id], []

    edges: list[tuple[str, bool]] = []
    anomalies: list[WiringAnomaly] = []
    seen: set[str] = set()
    for target in config.reads_cross_pole:
        if target in seen:
            continue
        seen.add(target)
        if target == config.id:
            anomalies.append(
                WiringAnomaly("self_reference", config.id, "se liste lui-même", "info")
            )
        elif target not in all_ids:
            anomalies.append(
                WiringAnomaly(
                    "orphan", config.id, f"lit un pôle inexistant : « {target} »", "warning"
                )
            )
        else:
            edges.append((target, False))
    return edges, anomalies


async def audit_wiring(*, poles_root: Path = POLES_DIR, now: datetime | None = None) -> WiringAudit:
    """Inspecte le câblage ``reads_cross_pole`` de tous les pôles publics."""
    moment = now or datetime.now(UTC)
    configs = load_all_poles(poles_root=poles_root)
    all_ids = {c.id for c in configs}

    facts_count: dict[str, int] = {}
    for cfg in configs:
        by_script = await read_pole_memory(cfg.id, poles_root=poles_root)
        facts_count[cfg.id] = sum(len(recs) for recs in by_script.values())

    edges: list[WiringEdge] = []
    anomalies: list[WiringAnomaly] = []
    for cfg in configs:
        targets, decl_anomalies = _resolve_targets(cfg, all_ids)
        anomalies.extend(decl_anomalies)
        for target, via_wildcard in targets:
            n = facts_count.get(target, 0)
            edges.append(WiringEdge(cfg.id, target, via_wildcard, n))
            # Un câblage EXPLICITE vers un pôle vide est à vide (le wildcard, lui,
            # lit « tout ce qui existera » — ne pas le bruiter sur chaque pôle vide).
            if not via_wildcard and n == 0:
                anomalies.append(
                    WiringAnomaly(
                        "empty_target", cfg.id, f"câblage à vide vers « {target} » (0 fait)", "info"
                    )
                )

    incoming = {e.target for e in edges}
    for cfg in configs:
        if facts_count.get(cfg.id, 0) > 0 and cfg.id not in incoming:
            anomalies.append(
                WiringAnomaly(
                    "unread_producer",
                    cfg.id,
                    f"produit {facts_count[cfg.id]} fait(s) mais personne ne le lit",
                    "warning",
                )
            )

    n_warn = sum(1 for a in anomalies if a.severity == "warning")
    should_alert = n_warn > 0
    summary = (
        f"Câblage sain — {len(edges)} arête(s), {len(all_ids)} pôle(s)."
        if not anomalies
        else f"{len(anomalies)} anomalie(s) ({n_warn} warning) sur {len(edges)} arête(s)."
    )
    return WiringAudit(
        generated_at=moment,
        poles=tuple(sorted(all_ids)),
        edges=tuple(edges),
        anomalies=tuple(anomalies),
        should_alert=should_alert,
        summary=summary,
    )


__all__ = [
    "AnomalyKind",
    "WiringAnomaly",
    "WiringAudit",
    "WiringEdge",
    "audit_wiring",
]
