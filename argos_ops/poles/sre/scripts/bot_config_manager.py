"""``BotConfigManagerScript`` — dérive de config de la flotte (archi v2, S8).

En archi v2 la config canonique d'un pôle **est** son ``pole.yaml`` (plus de DB
``agent_config`` — D-028). Ce script diffe la config *live* (tous les
``pole.yaml``) contre une baseline figée
(``data/poles/sre/config/baseline.yaml``) et alerte sur la dérive :

- agent changé / pôle ou script **disparu** → rouge (régression) ;
- pôle ou script **ajouté**, cadence ``schedule`` modifiée → jaune.

Pas de baseline ⇒ vert (rien à comparer). Pur fichiers, local-first.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml
from loguru import logger

from argos_ops.poles.config import POLES_DIR, load_all_poles
from argos_ops.poles.sre.base import BaseSreScript
from argos_ops.poles.sre.report import Severity, SreReport, worst

CONFIG_BASELINE = ("config", "baseline.yaml")
# Familles de dérive jugées critiques (rouge) — régression de capacité.
CRITICAL_KINDS = frozenset({"agent_changed", "script_removed", "pole_removed"})


def baseline_path(*, poles_root: Path = POLES_DIR) -> Path:
    return poles_root / "sre" / CONFIG_BASELINE[0] / CONFIG_BASELINE[1]


@dataclass(frozen=True)
class ConfigDrift:
    """Une divergence config live vs baseline."""

    pole: str
    kind: str  # agent_changed | script_added | script_removed | schedule_changed | pole_added | pole_removed
    detail: str

    @property
    def critical(self) -> bool:
        return self.kind in CRITICAL_KINDS


def _live_snapshot(*, poles_root: Path) -> dict[str, dict[str, object]]:
    """Construit la photo live : {pole: {agent, scripts:{id:schedule}}}."""
    out: dict[str, dict[str, object]] = {}
    for cfg in load_all_poles(poles_root=poles_root, include_internal=False):
        out[cfg.id] = {
            "agent": cfg.agent.name if cfg.agent else None,
            "scripts": {s.id: s.schedule for s in cfg.scripts},
        }
    return out


def _baseline_snapshot(*, poles_root: Path) -> dict[str, dict[str, object]] | None:
    path = baseline_path(poles_root=poles_root)
    if not path.exists():
        return None
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        logger.warning(f"bot_config_manager — baseline YAML invalide : {exc}")
        return None
    poles = raw.get("poles") if isinstance(raw, dict) else None
    if not isinstance(poles, dict):
        return None
    out: dict[str, dict[str, object]] = {}
    for pid, body in poles.items():
        if not isinstance(body, dict):
            continue
        scripts_raw = body.get("scripts")
        scripts = scripts_raw if isinstance(scripts_raw, dict) else {}
        out[str(pid)] = {"agent": body.get("agent"), "scripts": dict(scripts)}
    return out


def diff_config(
    baseline: dict[str, dict[str, object]], live: dict[str, dict[str, object]]
) -> list[ConfigDrift]:
    """Compare baseline et live (pur). Tri déterministe (pôle, kind)."""
    drifts: list[ConfigDrift] = []
    for pole in sorted(set(baseline) | set(live)):
        b = baseline.get(pole)
        live_p = live.get(pole)
        if b is None and live_p is not None:
            drifts.append(ConfigDrift(pole, "pole_added", f"pôle '{pole}' absent de la baseline"))
            continue
        if live_p is None and b is not None:
            drifts.append(
                ConfigDrift(pole, "pole_removed", f"pôle '{pole}' disparu (était baseliné)")
            )
            continue
        assert b is not None and live_p is not None
        if b.get("agent") != live_p.get("agent"):
            drifts.append(
                ConfigDrift(
                    pole, "agent_changed", f"agent {b.get('agent')} → {live_p.get('agent')}"
                )
            )
        b_scripts = b.get("scripts", {})
        live_scripts = live_p.get("scripts", {})
        assert isinstance(b_scripts, dict) and isinstance(live_scripts, dict)
        for sid in sorted(set(b_scripts) | set(live_scripts)):
            if sid not in live_scripts:
                drifts.append(ConfigDrift(pole, "script_removed", f"script '{sid}' supprimé"))
            elif sid not in b_scripts:
                drifts.append(ConfigDrift(pole, "script_added", f"script '{sid}' ajouté"))
            elif b_scripts[sid] != live_scripts[sid]:
                drifts.append(
                    ConfigDrift(
                        pole,
                        "schedule_changed",
                        f"'{sid}' cadence {b_scripts[sid]} → {live_scripts[sid]}",
                    )
                )
    return drifts


def build_report(
    baseline: dict[str, dict[str, object]] | None, drifts: list[ConfigDrift]
) -> SreReport:
    if baseline is None:
        return SreReport("green", "Aucune baseline de config (rien à comparer).")
    if not drifts:
        return SreReport("green", "Config alignée sur la baseline.")
    n_critical = sum(1 for d in drifts if d.critical)
    severity: Severity = worst("red" if n_critical else "green", "yellow")
    summary = f"{len(drifts)} dérive(s) de config · {n_critical} critique(s)"
    detail = "\n".join(f"- [{d.pole}] {d.kind} : {d.detail}" for d in drifts[:20])
    return SreReport(severity, summary, detail)


class BotConfigManagerScript(BaseSreScript):
    """Diffe la config live des pôles vs la baseline figée."""

    name = "bot_config_manager"

    async def check(self) -> SreReport:
        baseline = _baseline_snapshot(poles_root=self.poles_root)
        live = _live_snapshot(poles_root=self.poles_root)
        drifts = diff_config(baseline, live) if baseline is not None else []
        return build_report(baseline, drifts)


__all__ = [
    "CRITICAL_KINDS",
    "BotConfigManagerScript",
    "ConfigDrift",
    "baseline_path",
    "build_report",
    "diff_config",
]
