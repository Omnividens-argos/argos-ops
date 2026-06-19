"""Pipeline commercial du pôle Vente (archi v2, S4) — deals + scoring de risque.

Charge le pipe ``data/poles/vente/deals/pipe.yaml`` (saisi à la main par le
fondateur, **lecture seule** par les bots) et réutilise le scoring pur
:func:`argos_ops.sales.scoring.score_deal_risk` pour produire un risque 0-100 et
le flag ``stalled`` par stade. Sert le Kanban + la colonne « risque » du cockpit.

100 % fichiers / local-first (D-017) : aucune écriture, aucun LLM. Le pipe est la
source de vérité humaine ; le pôle ne fait que le lire et le qualifier.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import yaml
from loguru import logger

from argos_ops.poles.config import POLES_DIR
from argos_ops.poles.vente.store import parse_date
from argos_ops.sales.models import Deal, DealStage, DealStalledFlag
from argos_ops.sales.scoring import score_deal_risk

VENTE_POLE = "vente"

# Ordre canonique des colonnes Kanban (les stades terminaux won/lost en bout).
STAGE_ORDER: tuple[DealStage, ...] = (
    DealStage.DISCOVERY,
    DealStage.DEMO_SCHEDULED,
    DealStage.DEMO_DONE,
    DealStage.PROPOSAL_SENT,
    DealStage.CONTRACT_SENT,
    DealStage.WON,
    DealStage.LOST,
)
_ACTIVE_STAGES: frozenset[DealStage] = frozenset(STAGE_ORDER) - {DealStage.WON, DealStage.LOST}


def pipe_path(*, poles_root: Path = POLES_DIR) -> Path:
    return poles_root / VENTE_POLE / "deals" / "pipe.yaml"


def load_deals(*, poles_root: Path = POLES_DIR) -> list[Deal]:
    """Charge le pipe depuis ``deals/pipe.yaml``. Best-effort : pipe absent ⇒ ``[]``.

    Un stade inconnu est ignoré (logué) plutôt que de faire crasher tout le pôle —
    le pipe est saisi à la main et une coquille ne doit pas casser le cockpit.
    """
    path = pipe_path(poles_root=poles_root)
    if not path.exists():
        return []
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    entries = raw.get("deals", []) if isinstance(raw, dict) else []
    out: list[Deal] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        try:
            out.append(
                Deal(
                    deal_id=str(entry["deal_id"]),
                    company=str(entry["company"]),
                    stage=DealStage(str(entry["stage"])),
                    amount_eur=int(entry.get("amount_eur", 0)),
                    last_activity_at=parse_date(entry["last_activity_at"]),
                    owner=str(entry.get("owner", "founder")),
                    notes=(str(entry["notes"]) if entry.get("notes") is not None else None),
                )
            )
        except (KeyError, ValueError) as exc:
            logger.warning(f"pipeline — deal ignoré ({type(exc).__name__}: {exc}) : {entry!r}")
    return out


class DealNotFoundError(LookupError):
    """Aucun deal ne porte le ``deal_id`` demandé dans le pipe."""


def set_deal_stage(deal_id: str, stage: DealStage, *, poles_root: Path = POLES_DIR) -> Deal:
    """Déplace un deal vers ``stage`` (drag-drop Kanban) et ré-écrit ``pipe.yaml``.

    Ré-écriture chirurgicale : on relit le YAML brut et on ne touche **que** le
    champ ``stage`` de l'entrée ciblée — tous les autres champs et l'ordre des
    deals sont préservés. Lève :class:`DealNotFoundError` si ``deal_id`` est
    inconnu (le routeur le mappe en 404). Renvoie le :class:`Deal` à jour.
    """
    path = pipe_path(poles_root=poles_root)
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) if path.exists() else None
    raw = raw if isinstance(raw, dict) else {}
    entries = raw.get("deals")
    entries = entries if isinstance(entries, list) else []
    target: dict[str, object] | None = None
    for entry in entries:
        if isinstance(entry, dict) and str(entry.get("deal_id")) == deal_id:
            target = entry
            break
    if target is None:
        raise DealNotFoundError(deal_id)
    target["stage"] = stage.value
    raw["deals"] = entries
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(raw, allow_unicode=True, sort_keys=False), encoding="utf-8")
    logger.info(f"pipeline — deal {deal_id} déplacé vers {stage.value}")
    updated = next(d for d in load_deals(poles_root=poles_root) if d.deal_id == deal_id)
    return updated


def score_pipeline(deals: list[Deal], *, today: date | None = None) -> list[DealStalledFlag]:
    """Score chaque deal, trié du plus risqué au moins risqué (stable)."""
    flags = [score_deal_risk(d, today=today) for d in deals]
    flags.sort(key=lambda f: f.risk_score, reverse=True)
    return flags


def stalled_active(flags: list[DealStalledFlag]) -> list[DealStalledFlag]:
    """Les deals encore dans le pipe actif (hors won/lost) et flag stalled."""
    return [f for f in flags if f.is_stalled and f.deal.stage in _ACTIVE_STAGES]


def pipeline_value_eur(deals: list[Deal]) -> int:
    """Valeur cumulée (MRR annualisé) des deals actifs (hors won/lost)."""
    return sum(d.amount_eur for d in deals if d.stage in _ACTIVE_STAGES)


__all__ = [
    "STAGE_ORDER",
    "DealNotFoundError",
    "load_deals",
    "pipe_path",
    "pipeline_value_eur",
    "score_pipeline",
    "set_deal_stage",
    "stalled_active",
]
