"""Comptes clients du pôle Vente (archi v2, S4) — santé / churn / upsell.

Charge ``data/poles/vente/cs/customers.yaml`` via le loader partagé
:func:`argos_ops.cs.loader.load_customers` et réutilise les scorings purs et
**auditables** (RGPD § 22) de :mod:`argos_ops.cs.scoring` :
:func:`compute_health_score`, :func:`detect_churn_signals`,
:func:`detect_upsell_candidate`.

100 % fichiers / local-first (D-017) : le YAML est saisi à la main par le
fondateur (lecture seule), le pôle ne fait que scorer et exposer les vues.
"""

from __future__ import annotations

from pathlib import Path

from argos_ops.cs.loader import load_customers
from argos_ops.cs.models import ChurnSignal, Customer, HealthScore, UpsellCandidate
from argos_ops.cs.scoring import (
    compute_health_score,
    detect_churn_signals,
    detect_upsell_candidate,
)
from argos_ops.poles.config import POLES_DIR

VENTE_POLE = "vente"

# Score churn au-delà duquel un compte est traité comme urgent (action < 48h).
URGENT_CHURN_THRESHOLD = 60


def customers_path(*, poles_root: Path = POLES_DIR) -> Path:
    return poles_root / VENTE_POLE / "cs" / "customers.yaml"


def load_accounts(*, poles_root: Path = POLES_DIR) -> list[Customer]:
    """Charge les comptes clients. Absent ⇒ ``[]`` (best-effort)."""
    return load_customers(customers_path(poles_root=poles_root))


def score_health(customers: list[Customer]) -> list[HealthScore]:
    """Score santé de chaque compte, trié du plus bas (à risque) au plus haut."""
    scores = [compute_health_score(c) for c in customers]
    scores.sort(key=lambda h: h.score)
    return scores


def detect_churn(customers: list[Customer]) -> list[ChurnSignal]:
    """Signaux pré-churn (comptes sains exclus), triés du plus risqué au moins."""
    signals = [s for c in customers if (s := detect_churn_signals(c)) is not None]
    signals.sort(key=lambda s: s.risk_score, reverse=True)
    return signals


def detect_upsells(customers: list[Customer]) -> list[UpsellCandidate]:
    """Candidats upsell (usage ≥ 80% quota), triés du plus saturé au moins."""
    cands = [u for c in customers if (u := detect_upsell_candidate(c)) is not None]
    cands.sort(key=lambda u: u.usage_ratio, reverse=True)
    return cands


__all__ = [
    "URGENT_CHURN_THRESHOLD",
    "customers_path",
    "detect_churn",
    "detect_upsells",
    "load_accounts",
    "score_health",
]
