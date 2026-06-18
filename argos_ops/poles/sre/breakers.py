"""Registre **fichier** des circuit breakers du pôle SRE (archi v2, S8).

Généralise le breaker latch du pôle Pub (:mod:`argos_ops.poles.pub.budget`) en un
registre nommé local-first (``data/poles/sre/breakers.yaml``) — pas de DB,
contrairement au breaker legacy :mod:`argos_ops.breakers`.

Sémantique **latch** : un breaker armé le reste jusqu'à un reset humain (cockpit
/ ``/reset-breaker``), même si la condition qui l'a armé a disparu. Le script
``kill_switch_operator`` surveille les breakers armés depuis trop longtemps ;
l'orchestrateur saute un script dont le breaker éponyme est armé.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import yaml
from loguru import logger

from argos_ops.poles.config import POLES_DIR

SRE_POLE = "sre"
BREAKERS_FILE = "breakers.yaml"


def breakers_path(*, poles_root: Path = POLES_DIR) -> Path:
    return poles_root / SRE_POLE / BREAKERS_FILE


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
class Breaker:
    """État latch d'un circuit breaker nommé."""

    name: str
    tripped: bool = False
    reason: str | None = None
    tripped_at: datetime | None = None
    updated_at: datetime | None = None

    @property
    def age_hours(self) -> float | None:
        """Heures écoulées depuis l'armement (``None`` si non armé)."""
        if not self.tripped or self.tripped_at is None:
            return None
        return (_utcnow() - self.tripped_at).total_seconds() / 3600.0


def load_breakers(*, poles_root: Path = POLES_DIR) -> dict[str, Breaker]:
    """Charge tous les breakers (``{}`` si fichier absent / malformé)."""
    path = breakers_path(poles_root=poles_root)
    if not path.exists():
        return {}
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        logger.warning(f"sre.breakers — YAML invalide, registre vide : {exc}")
        return {}
    entries = raw.get("breakers") if isinstance(raw, dict) else None
    if not isinstance(entries, dict):
        return {}
    out: dict[str, Breaker] = {}
    for name, body in entries.items():
        if not isinstance(body, dict):
            continue
        out[str(name)] = Breaker(
            name=str(name),
            tripped=bool(body.get("tripped", False)),
            reason=(str(body["reason"]) if body.get("reason") else None),
            tripped_at=_parse_dt(body.get("tripped_at")),
            updated_at=_parse_dt(body.get("updated_at")),
        )
    return out


def save_breakers(breakers: dict[str, Breaker], *, poles_root: Path = POLES_DIR) -> None:
    """Persiste le registre (tri par nom pour un YAML déterministe)."""
    path = breakers_path(poles_root=poles_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "breakers": {
            b.name: {
                "tripped": b.tripped,
                "reason": b.reason,
                "tripped_at": b.tripped_at.isoformat() if b.tripped_at else None,
                "updated_at": b.updated_at.isoformat() if b.updated_at else None,
            }
            for b in sorted(breakers.values(), key=lambda x: x.name)
        }
    }
    path.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=True), encoding="utf-8")
    logger.debug(f"sre.breakers — {len(breakers)} breaker(s) sauvegardé(s)")


def get_breaker(name: str, *, poles_root: Path = POLES_DIR) -> Breaker:
    """Renvoie l'état d'un breaker (non armé par défaut s'il n'existe pas)."""
    return load_breakers(poles_root=poles_root).get(name, Breaker(name=name))


def is_tripped(name: str, *, poles_root: Path = POLES_DIR) -> bool:
    return get_breaker(name, poles_root=poles_root).tripped


def list_tripped(*, poles_root: Path = POLES_DIR) -> list[Breaker]:
    """Breakers armés, du plus ancien armement au plus récent."""
    tripped = [b for b in load_breakers(poles_root=poles_root).values() if b.tripped]
    tripped.sort(key=lambda b: b.tripped_at or _utcnow())
    return tripped


def trip(
    name: str, reason: str, *, now: datetime | None = None, poles_root: Path = POLES_DIR
) -> Breaker:
    """Arme un breaker (latch). Conserve ``tripped_at`` s'il était déjà armé."""
    moment = now or _utcnow()
    breakers = load_breakers(poles_root=poles_root)
    prev = breakers.get(name)
    updated = Breaker(
        name=name,
        tripped=True,
        reason=reason,
        tripped_at=(prev.tripped_at if prev and prev.tripped and prev.tripped_at else moment),
        updated_at=moment,
    )
    breakers[name] = updated
    save_breakers(breakers, poles_root=poles_root)
    logger.info(f"sre.breakers — '{name}' armé : {reason}")
    return updated


def reset(name: str, *, now: datetime | None = None, poles_root: Path = POLES_DIR) -> Breaker:
    """Désarme un breaker (reset humain)."""
    moment = now or _utcnow()
    breakers = load_breakers(poles_root=poles_root)
    updated = Breaker(name=name, tripped=False, reason=None, tripped_at=None, updated_at=moment)
    breakers[name] = updated
    save_breakers(breakers, poles_root=poles_root)
    logger.info(f"sre.breakers — '{name}' désarmé")
    return updated


__all__ = [
    "BREAKERS_FILE",
    "Breaker",
    "breakers_path",
    "get_breaker",
    "is_tripped",
    "list_tripped",
    "load_breakers",
    "reset",
    "save_breakers",
    "trip",
]
