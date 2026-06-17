"""Garde-fous **budget** du pôle Pub + circuit breaker ``ad_spend_runaway`` (S3).

Cœur du pôle Pub : la dépense publicitaire est plafonnée par un budget
journalier (réglé par le fondateur) et surveillée par un **circuit breaker**
``ad_spend_runaway``. Tout est *fichier* (``data/poles/pub/budget.yaml``,
local-first D-017) — pas de DB, contrairement au breaker legacy
:mod:`argos_ops.breakers`.

Sémantique du breaker (calquée sur le legacy) : **latch**. Le script
``ads_optimizer`` l'arme dès que la dépense moyenne/jour dépasse
``daily_budget x runaway_multiplier`` (1,5 par défaut) ; il **reste armé**
jusqu'à un reset humain (cockpit / ``/reset-breaker``), même si une mesure
ultérieure repasse sous le seuil. C'est le garde-fou « Python tranche » que
:class:`~argos_ops.poles.pub.agent.PubAgent` consulte pour brider son plan.

La **jauge** (dépensé/jour vs budget) est, elle, recalculée à chaud depuis le
dernier export de campagnes — le breaker est l'état persistant, la jauge est la
photo du moment.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import yaml
from loguru import logger

from argos_ops.poles.config import POLES_DIR

PUB_POLE = "pub"
BUDGET_FILENAME = "budget.yaml"
BREAKER_NAME = "ad_spend_runaway"

DEFAULT_RUNAWAY_MULTIPLIER = 1.5
DEFAULT_WINDOW_DAYS = 7


def _utcnow() -> datetime:
    return datetime.now(UTC)


# =============================================================================
# État du budget (config founder + dépense calculée + latch breaker)
# =============================================================================
@dataclass(frozen=True)
class Budget:
    """Photo du budget pub : config, dépense mesurée et état du breaker.

    ``daily_budget_eur <= 0`` ⇒ budget **non réglé** : la jauge et le breaker
    sont neutralisés (pas de faux déclenchement tant que le fondateur n'a pas
    fixé d'enveloppe).
    """

    daily_budget_eur: float = 0.0
    runaway_multiplier: float = DEFAULT_RUNAWAY_MULTIPLIER
    window_days: int = DEFAULT_WINDOW_DAYS
    spent_per_day_eur: float = 0.0
    spent_window_eur: float = 0.0
    by_platform: dict[str, float] = field(default_factory=dict)
    breaker_tripped: bool = False
    breaker_reason: str | None = None
    breaker_tripped_at: datetime | None = None
    updated_at: datetime = field(default_factory=_utcnow)

    @property
    def is_set(self) -> bool:
        return self.daily_budget_eur > 0

    @property
    def runaway_threshold_eur(self) -> float:
        """Seuil d'emballement = budget/jour x multiplicateur (0 si non réglé)."""
        return self.daily_budget_eur * self.runaway_multiplier if self.is_set else 0.0

    @property
    def utilization(self) -> float:
        """Part du budget journalier consommée (0 si budget non réglé)."""
        return self.spent_per_day_eur / self.daily_budget_eur if self.is_set else 0.0

    @property
    def over_threshold(self) -> bool:
        """La dépense/jour mesurée dépasse-t-elle le seuil d'emballement *maintenant* ?

        État *live* (photo) distinct du latch ``breaker_tripped`` : un breaker
        peut rester armé alors que la dépense est repassée sous le seuil.
        """
        return self.is_set and self.spent_per_day_eur > self.runaway_threshold_eur


# =============================================================================
# Évaluation pure
# =============================================================================
def runaway_threshold(
    daily_budget_eur: float, *, multiplier: float = DEFAULT_RUNAWAY_MULTIPLIER
) -> float:
    return daily_budget_eur * multiplier if daily_budget_eur > 0 else 0.0


def evaluate_runaway(
    daily_budget_eur: float,
    spent_per_day_eur: float,
    *,
    multiplier: float = DEFAULT_RUNAWAY_MULTIPLIER,
) -> bool:
    """Le breaker ``ad_spend_runaway`` *devrait-il* être armé ? Pure.

    ``True`` ssi un budget est réglé (> 0) et la dépense moyenne/jour dépasse
    ``daily_budget x multiplier``.
    """
    if daily_budget_eur <= 0:
        return False
    return spent_per_day_eur > runaway_threshold(daily_budget_eur, multiplier=multiplier)


# =============================================================================
# Persistance (budget.yaml)
# =============================================================================
def budget_path(*, poles_root: Path = POLES_DIR) -> Path:
    return poles_root / PUB_POLE / BUDGET_FILENAME


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


def load_budget(*, poles_root: Path = POLES_DIR) -> Budget:
    """Charge ``budget.yaml`` (valeurs par défaut si absent / malformé)."""
    path = budget_path(poles_root=poles_root)
    if not path.exists():
        return Budget()
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        logger.warning(f"budget — YAML invalide, défauts utilisés : {exc}")
        return Budget()
    if not isinstance(raw, dict):
        return Budget()

    spend = raw.get("spend")
    if not isinstance(spend, dict):
        spend = {}
    breaker = raw.get("breaker")
    if not isinstance(breaker, dict):
        breaker = {}
    raw_by_platform = spend.get("by_platform")
    if not isinstance(raw_by_platform, dict):
        raw_by_platform = {}

    # Coercions tolérantes : une valeur hand-corrompue (``daily_budget_eur: "abc"``)
    # ne doit jamais faire crasher la lecture du breaker (chemin chaud : agent,
    # cockpit, scripts). On retombe sur les défauts.
    try:
        by_platform = {str(k): float(v) for k, v in raw_by_platform.items()}
        return Budget(
            daily_budget_eur=float(raw.get("daily_budget_eur") or 0.0),
            runaway_multiplier=float(raw.get("runaway_multiplier") or DEFAULT_RUNAWAY_MULTIPLIER),
            window_days=int(raw.get("window_days") or DEFAULT_WINDOW_DAYS),
            spent_per_day_eur=float(spend.get("per_day_eur") or 0.0),
            spent_window_eur=float(spend.get("window_eur") or 0.0),
            by_platform=by_platform,
            breaker_tripped=bool(breaker.get("tripped", False)),
            breaker_reason=(str(breaker["reason"]) if breaker.get("reason") else None),
            breaker_tripped_at=_parse_dt(breaker.get("tripped_at")),
            updated_at=_parse_dt(raw.get("updated_at")) or _utcnow(),
        )
    except (ValueError, TypeError) as exc:
        logger.warning(f"budget — valeur non numérique, défauts utilisés : {exc}")
        return Budget()


def save_budget(budget: Budget, *, poles_root: Path = POLES_DIR) -> Budget:
    """Persiste l'état du budget en YAML (crée le dossier au besoin)."""
    path = budget_path(poles_root=poles_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "daily_budget_eur": budget.daily_budget_eur,
        "runaway_multiplier": budget.runaway_multiplier,
        "window_days": budget.window_days,
        "spend": {
            "per_day_eur": round(budget.spent_per_day_eur, 2),
            "window_eur": round(budget.spent_window_eur, 2),
            "by_platform": {k: round(v, 2) for k, v in sorted(budget.by_platform.items())},
        },
        "breaker": {
            "tripped": budget.breaker_tripped,
            "reason": budget.breaker_reason,
            "tripped_at": budget.breaker_tripped_at.isoformat()
            if budget.breaker_tripped_at
            else None,
        },
        "updated_at": budget.updated_at.isoformat(),
    }
    path.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=True), encoding="utf-8")
    logger.debug(f"budget — sauvegardé (tripped={budget.breaker_tripped})")
    return budget


# =============================================================================
# Mutations (config / dépense / breaker)
# =============================================================================
def set_daily_budget(daily_budget_eur: float, *, poles_root: Path = POLES_DIR) -> Budget:
    """Règle l'enveloppe journalière (cockpit). Ne touche pas au breaker."""
    prev = load_budget(poles_root=poles_root)
    updated = Budget(
        daily_budget_eur=max(0.0, daily_budget_eur),
        runaway_multiplier=prev.runaway_multiplier,
        window_days=prev.window_days,
        spent_per_day_eur=prev.spent_per_day_eur,
        spent_window_eur=prev.spent_window_eur,
        by_platform=prev.by_platform,
        breaker_tripped=prev.breaker_tripped,
        breaker_reason=prev.breaker_reason,
        breaker_tripped_at=prev.breaker_tripped_at,
        updated_at=_utcnow(),
    )
    return save_budget(updated, poles_root=poles_root)


def update_spend(
    by_platform: dict[str, float],
    *,
    window_days: int,
    poles_root: Path = POLES_DIR,
    now: datetime | None = None,
) -> Budget:
    """Met à jour la dépense mesurée et **arme** le breaker en cas d'emballement.

    Latch : si le breaker était déjà armé, il le reste (on ne dé-arme jamais
    automatiquement — c'est le reset humain qui le fait).
    """
    moment = now or _utcnow()
    prev = load_budget(poles_root=poles_root)
    window = max(1, window_days)
    spent_window = sum(by_platform.values())
    spent_per_day = spent_window / window

    should_trip = evaluate_runaway(
        prev.daily_budget_eur, spent_per_day, multiplier=prev.runaway_multiplier
    )
    tripped = prev.breaker_tripped or should_trip
    reason = prev.breaker_reason
    tripped_at = prev.breaker_tripped_at
    if should_trip and not prev.breaker_tripped:
        reason = (
            f"Dépense {spent_per_day:.2f} €/j > seuil "
            f"{runaway_threshold(prev.daily_budget_eur, multiplier=prev.runaway_multiplier):.2f} €/j "
            f"(budget {prev.daily_budget_eur:.2f} €/j x {prev.runaway_multiplier})"
        )
        tripped_at = moment

    updated = Budget(
        daily_budget_eur=prev.daily_budget_eur,
        runaway_multiplier=prev.runaway_multiplier,
        window_days=window,
        spent_per_day_eur=spent_per_day,
        spent_window_eur=spent_window,
        by_platform={k: float(v) for k, v in by_platform.items()},
        breaker_tripped=tripped,
        breaker_reason=reason,
        breaker_tripped_at=tripped_at,
        updated_at=moment,
    )
    return save_budget(updated, poles_root=poles_root)


def reset_breaker(*, poles_root: Path = POLES_DIR) -> Budget:
    """Désarme le breaker (reset humain). Conserve la dépense mesurée."""
    prev = load_budget(poles_root=poles_root)
    updated = Budget(
        daily_budget_eur=prev.daily_budget_eur,
        runaway_multiplier=prev.runaway_multiplier,
        window_days=prev.window_days,
        spent_per_day_eur=prev.spent_per_day_eur,
        spent_window_eur=prev.spent_window_eur,
        by_platform=prev.by_platform,
        breaker_tripped=False,
        breaker_reason=None,
        breaker_tripped_at=None,
        updated_at=_utcnow(),
    )
    return save_budget(updated, poles_root=poles_root)


# =============================================================================
# Simulateur de budget (pure)
# =============================================================================
@dataclass(frozen=True)
class SimAllocation:
    """Projection d'une enveloppe journalière allouée à une plateforme."""

    platform: str
    daily_eur: float
    cpa_eur: float
    weekly_spend_eur: float
    weekly_leads: float


@dataclass(frozen=True)
class Simulation:
    """Résultat du simulateur : projection hebdo + verdict garde-fous."""

    total_daily_eur: float
    weekly_spend_eur: float
    weekly_leads: float
    blended_cpa_eur: float
    exceeds_budget: bool
    would_trip: bool
    allocations: tuple[SimAllocation, ...]


def simulate_budget(
    per_platform_daily: dict[str, float],
    *,
    daily_budget_eur: float,
    cpa_by_platform: dict[str, float],
    multiplier: float = DEFAULT_RUNAWAY_MULTIPLIER,
    days: int = DEFAULT_WINDOW_DAYS,
) -> Simulation:
    """Projette une allocation budgétaire par plateforme sur ``days`` jours.

    Pour chaque plateforme : leads projetés = dépense / CPA observé (0 si CPA
    inconnu / nul). ``exceeds_budget`` compare le total journalier à l'enveloppe ;
    ``would_trip`` au seuil d'emballement (x multiplicateur). Pure — le CPA
    observé est fourni par l'appelant (dérivé du dernier CSV).
    """
    span = max(1, days)
    allocations: list[SimAllocation] = []
    total_daily = 0.0
    weekly_spend = 0.0
    weekly_leads = 0.0
    for platform, daily in sorted(per_platform_daily.items()):
        daily = max(0.0, float(daily))
        cpa = max(0.0, float(cpa_by_platform.get(platform, 0.0)))
        spend = daily * span
        leads = spend / cpa if cpa > 0 else 0.0
        allocations.append(
            SimAllocation(
                platform=platform,
                daily_eur=daily,
                cpa_eur=cpa,
                weekly_spend_eur=spend,
                weekly_leads=leads,
            )
        )
        total_daily += daily
        weekly_spend += spend
        weekly_leads += leads

    blended_cpa = weekly_spend / weekly_leads if weekly_leads > 0 else 0.0
    return Simulation(
        total_daily_eur=total_daily,
        weekly_spend_eur=weekly_spend,
        weekly_leads=weekly_leads,
        blended_cpa_eur=blended_cpa,
        exceeds_budget=daily_budget_eur > 0 and total_daily > daily_budget_eur,
        would_trip=evaluate_runaway(daily_budget_eur, total_daily, multiplier=multiplier),
        allocations=tuple(allocations),
    )


__all__ = [
    "BREAKER_NAME",
    "DEFAULT_RUNAWAY_MULTIPLIER",
    "DEFAULT_WINDOW_DAYS",
    "Budget",
    "SimAllocation",
    "Simulation",
    "budget_path",
    "evaluate_runaway",
    "load_budget",
    "reset_breaker",
    "runaway_threshold",
    "save_budget",
    "set_daily_budget",
    "simulate_budget",
    "update_spend",
]
