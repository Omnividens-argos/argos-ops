"""Kill-switch **fichier** de la flotte (archi v2, S8).

Garde-fou global du pôle SRE : un interrupteur d'arrêt local-first
(``data/poles/sre/killswitch.yaml``) qui **gèle** l'exécution — soit toute la
flotte (``frozen: true``), soit une liste de scripts ciblés (``frozen_scripts``).

Consommé par :func:`argos_ops.poles.sre.base.run_sre_script` (un script gelé ne
tourne pas, son run est journalisé ``skipped``) et par l'orchestrateur (verdict
``skipped_frozen``). Le cockpit lit/écrit cet état (onglet Kill-switch).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import yaml
from loguru import logger

from argos_ops.poles.config import POLES_DIR

SRE_POLE = "sre"
KILLSWITCH_FILE = "killswitch.yaml"


def killswitch_path(*, poles_root: Path = POLES_DIR) -> Path:
    return poles_root / SRE_POLE / KILLSWITCH_FILE


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _parse_dt(value: object) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    try:
        dt = datetime.fromisoformat(str(value))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


@dataclass(frozen=True)
class KillSwitch:
    """État de l'interrupteur d'arrêt de la flotte."""

    frozen: bool = False
    reason: str | None = None
    frozen_scripts: tuple[str, ...] = ()
    updated_at: datetime | None = field(default=None)

    def is_frozen(self, script: str) -> bool:
        """Le script est-il gelé (gel global OU gel ciblé) ?"""
        return self.frozen or script in self.frozen_scripts


def load_killswitch(*, poles_root: Path = POLES_DIR) -> KillSwitch:
    """Charge l'état (désactivé par défaut si fichier absent / malformé)."""
    path = killswitch_path(poles_root=poles_root)
    if not path.exists():
        return KillSwitch()
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        logger.warning(f"sre.killswitch — YAML invalide, gel désactivé : {exc}")
        return KillSwitch()
    if not isinstance(raw, dict):
        return KillSwitch()
    scripts = raw.get("frozen_scripts")
    frozen_scripts = tuple(str(s) for s in scripts) if isinstance(scripts, list) else ()
    return KillSwitch(
        frozen=bool(raw.get("frozen", False)),
        reason=(str(raw["reason"]) if raw.get("reason") else None),
        frozen_scripts=frozen_scripts,
        updated_at=_parse_dt(raw.get("updated_at")),
    )


def save_killswitch(ks: KillSwitch, *, poles_root: Path = POLES_DIR) -> KillSwitch:
    """Persiste l'état (scripts triés pour un YAML déterministe)."""
    path = killswitch_path(poles_root=poles_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "frozen": ks.frozen,
        "reason": ks.reason,
        "frozen_scripts": sorted(ks.frozen_scripts),
        "updated_at": (ks.updated_at or _utcnow()).isoformat(),
    }
    path.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=True), encoding="utf-8")
    logger.info(f"sre.killswitch — global={ks.frozen}, {len(ks.frozen_scripts)} script(s) gelé(s)")
    return ks


def set_global(
    frozen: bool,
    *,
    reason: str | None = None,
    now: datetime | None = None,
    poles_root: Path = POLES_DIR,
) -> KillSwitch:
    """(Dé)gèle toute la flotte. Conserve la liste des gels ciblés."""
    prev = load_killswitch(poles_root=poles_root)
    updated = KillSwitch(
        frozen=frozen,
        reason=reason if frozen else None,
        frozen_scripts=prev.frozen_scripts,
        updated_at=now or _utcnow(),
    )
    return save_killswitch(updated, poles_root=poles_root)


def set_script(
    script: str, frozen: bool, *, now: datetime | None = None, poles_root: Path = POLES_DIR
) -> KillSwitch:
    """(Dé)gèle un script ciblé. Idempotent."""
    prev = load_killswitch(poles_root=poles_root)
    current = set(prev.frozen_scripts)
    if frozen:
        current.add(script)
    else:
        current.discard(script)
    updated = KillSwitch(
        frozen=prev.frozen,
        reason=prev.reason,
        frozen_scripts=tuple(sorted(current)),
        updated_at=now or _utcnow(),
    )
    return save_killswitch(updated, poles_root=poles_root)


__all__ = [
    "KILLSWITCH_FILE",
    "KillSwitch",
    "killswitch_path",
    "load_killswitch",
    "save_killswitch",
    "set_global",
    "set_script",
]
