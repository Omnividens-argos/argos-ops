"""Journal des recommandations **appliquées** (shadow) du pôle Pub (archi v2, S3).

Quand le fondateur clique « appliquer » sur une reco chiffrée depuis le cockpit,
on enregistre ici la **décision** (un fichier ``data/poles/pub/applied/<id>.yaml``
par reco), sans rien pousser en plateforme (mode shadow D-026). Le cockpit relit
ce journal pour marquer les recos déjà appliquées ; le script ``ad_bot`` peut le
consommer pour matérialiser (en shadow) ce qu'il *pousserait* en live.

Idempotent : appliquer deux fois la même reco (même ``id``) préserve
``applied_at``. 100 % fichiers, local-first (D-017), aucune valeur secrète.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import yaml
from loguru import logger

from argos_ops.poles.config import POLES_DIR

PUB_POLE = "pub"
APPLIED_DIRNAME = "applied"


def _utcnow() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True)
class AppliedReco:
    """Trace d'une reco appliquée en shadow."""

    id: str
    platform: str
    campaign: str
    action: str
    eur_delta_week: float
    rationale: str
    mode: str = "shadow"
    applied_at: datetime = datetime(1970, 1, 1, tzinfo=UTC)


def applied_dir(*, poles_root: Path = POLES_DIR) -> Path:
    return poles_root / PUB_POLE / APPLIED_DIRNAME


def _applied_path(reco_id: str, *, poles_root: Path) -> Path:
    return applied_dir(poles_root=poles_root) / f"{reco_id}.yaml"


def _parse_dt(value: object) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    try:
        dt = datetime.fromisoformat(str(value))
    except (ValueError, TypeError):
        return _utcnow()
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def record_applied(
    *,
    reco_id: str,
    platform: str,
    campaign: str,
    action: str,
    eur_delta_week: float,
    rationale: str,
    poles_root: Path = POLES_DIR,
) -> AppliedReco:
    """Enregistre (idempotent) une reco appliquée en shadow."""
    path = _applied_path(reco_id, poles_root=poles_root)
    applied_at = _utcnow()
    if path.exists():
        try:
            prev = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            if isinstance(prev, dict) and prev.get("applied_at"):
                applied_at = _parse_dt(prev["applied_at"])
        except yaml.YAMLError:
            pass

    record = AppliedReco(
        id=reco_id,
        platform=platform,
        campaign=campaign,
        action=action,
        eur_delta_week=eur_delta_week,
        rationale=rationale,
        applied_at=applied_at,
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(
            {
                "id": record.id,
                "platform": record.platform,
                "campaign": record.campaign,
                "action": record.action,
                "eur_delta_week": record.eur_delta_week,
                "rationale": record.rationale,
                "mode": record.mode,
                "applied_at": record.applied_at.isoformat(),
            },
            sort_keys=False,
            allow_unicode=True,
        ),
        encoding="utf-8",
    )
    logger.debug(f"applied — {reco_id} (shadow)")
    return record


def load_applied(*, poles_root: Path = POLES_DIR) -> list[AppliedReco]:
    """Toutes les recos appliquées (du plus récent au plus ancien). Best-effort."""
    d = applied_dir(poles_root=poles_root)
    if not d.exists():
        return []
    out: list[AppliedReco] = []
    for path in d.glob("*.yaml"):
        try:
            raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            if not isinstance(raw, dict):
                continue
            out.append(
                AppliedReco(
                    id=str(raw.get("id") or path.stem),
                    platform=str(raw.get("platform") or ""),
                    campaign=str(raw.get("campaign") or ""),
                    action=str(raw.get("action") or ""),
                    eur_delta_week=float(raw.get("eur_delta_week") or 0.0),
                    rationale=str(raw.get("rationale") or ""),
                    mode=str(raw.get("mode") or "shadow"),
                    applied_at=_parse_dt(raw.get("applied_at")),
                )
            )
        except (yaml.YAMLError, ValueError, TypeError) as exc:
            logger.warning(f"applied — fichier illisible {path} : {exc}")
            continue
    out.sort(key=lambda a: a.applied_at, reverse=True)
    return out


def applied_ids(*, poles_root: Path = POLES_DIR) -> set[str]:
    """Ids des recos déjà appliquées (pour marquer la file du cockpit)."""
    return {a.id for a in load_applied(poles_root=poles_root)}


__all__ = [
    "AppliedReco",
    "applied_dir",
    "applied_ids",
    "load_applied",
    "record_applied",
]
