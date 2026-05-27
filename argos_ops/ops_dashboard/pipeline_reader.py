"""Reader du pipeline commercial pour l'Admin Control Panel (Phase 5 UX).

Source : ``data/sales/deals/pipe.yaml`` (saisi à la main par le fondateur,
mis à jour après chaque interaction client). Format documenté dans
``argos_ops/agents/deal_risk_scorer.py``.

Pas d'écriture — read-only. La gestion des deals se fait dans le YAML
directement (l'éditeur YAML du panel peut être étendu pour ça plus tard).
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import yaml
from loguru import logger

from argos_ops.ops_dashboard.models import PipelineDeal, PipelineSnapshot

# Seuils de risque (jours depuis dernière activité).
STALLED_DAYS = 14
AT_RISK_DAYS = 7

PIPE_REL_PATH = "data/sales/deals/pipe.yaml"


def _project_root() -> Path:
    """Racine du repo (parent de ``argos_ops/``)."""
    return Path(__file__).resolve().parents[2]


def _to_datetime(value: Any) -> datetime | None:
    """Tolère datetime / date / string ISO."""
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value
    if isinstance(value, date):
        return datetime.combine(value, datetime.min.time()).replace(tzinfo=UTC)
    if isinstance(value, str):
        for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                return datetime.strptime(value[: len(fmt) + 2], fmt).replace(tzinfo=UTC)
            except ValueError:
                continue
    return None


def _classify_risk(days_since_activity: int | None, stage: str) -> str:
    """Retourne 'stalled' / 'at_risk' / 'healthy' selon l'âge et le stade."""
    if stage in {"won", "lost"}:
        return "healthy"
    if days_since_activity is None:
        return "healthy"
    if days_since_activity >= STALLED_DAYS:
        return "stalled"
    if days_since_activity >= AT_RISK_DAYS:
        return "at_risk"
    return "healthy"


def read_pipeline() -> PipelineSnapshot:
    """Lit le pipe YAML et retourne le snapshot pour l'API.

    Si le fichier est absent ou vide → ``has_data=False`` (l'UI affichera
    un empty state explicatif avec un YAML d'exemple).
    """
    root = _project_root()
    path = (root / PIPE_REL_PATH).resolve()
    try:
        path.relative_to(root.resolve())
    except ValueError:
        # Sécurité : devrait jamais arriver, mais évite tout escape.
        logger.warning("pipeline_reader: path escapes repo root: {}", path)
        return _empty_snapshot()

    if not path.is_file():
        return _empty_snapshot()

    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        logger.warning("pipeline_reader: YAML invalide dans {} → {}", path, exc)
        return _empty_snapshot()

    deals_raw = raw.get("deals", []) if isinstance(raw, dict) else []
    deals: list[PipelineDeal] = []
    now = datetime.now(UTC)
    total_amount = 0.0
    for entry in deals_raw:
        if not isinstance(entry, dict):
            continue
        last_activity = _to_datetime(entry.get("last_activity_at"))
        days = (now - last_activity).days if last_activity else None
        stage = str(entry.get("stage") or "discovery")
        amount = entry.get("amount_eur")
        amount_float = float(amount) if amount is not None else None
        deals.append(
            PipelineDeal(
                deal_id=str(entry.get("deal_id") or f"deal-{len(deals)+1}"),
                company=str(entry.get("company") or "?"),
                stage=stage,
                amount_eur=amount_float,
                last_activity_at=last_activity,
                days_since_activity=days,
                owner=entry.get("owner"),
                notes=entry.get("notes"),
                risk_level=_classify_risk(days, stage),
            )
        )
        if amount_float is not None and stage not in {"lost"}:
            total_amount += amount_float

    return PipelineSnapshot(
        has_data=len(deals) > 0,
        file_path=PIPE_REL_PATH,
        total_deals=len(deals),
        total_amount_eur=total_amount,
        deals=deals,
        last_refreshed_at=now,
    )


def _empty_snapshot() -> PipelineSnapshot:
    return PipelineSnapshot(
        has_data=False,
        file_path=PIPE_REL_PATH,
        total_deals=0,
        total_amount_eur=0.0,
        deals=[],
        last_refreshed_at=datetime.now(UTC),
    )


__all__ = ["AT_RISK_DAYS", "PIPE_REL_PATH", "STALLED_DAYS", "read_pipeline"]
