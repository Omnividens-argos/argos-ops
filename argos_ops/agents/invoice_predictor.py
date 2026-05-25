"""InvoicePredictor — Trésorier (Sprint 10).

Lit les subscriptions Stripe actives et écrit un forecast cash flow
30 / 60 / 90 jours dans ``data/finance/forecast_<YYYY-MM-DD>.md``.

Politique notification : aucun push Discord automatique — le forecast
est consommé par le founder ou par BurnRateMonitor (qui le combine
avec le burn pour calculer le runway).

L'agent est idempotent à la date — ré-exécuter le même jour écrase
le fichier de forecast existant. Pas de breaker dédié (pas de risque
métier).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from loguru import logger

from argos_ops.agents.base import BaseAgent, RunResult
from argos_ops.config import REPO_ROOT, get_settings
from argos_ops.exceptions import AgentDataSourceError, AgentOutputError, ConfigError
from argos_ops.finance.cash_flow import CashFlowForecast, forecast_cash_flow
from argos_ops.integrations.stripe_client import (
    StripeSubscription,
    fetch_active_subscriptions,
)

DEFAULT_FORECAST_DIR: Path = REPO_ROOT / "data" / "finance"


@dataclass(frozen=True)
class InvoicePredictionRun:
    """Résultat d'un run InvoicePredictor — pour observabilité."""

    forecast: CashFlowForecast
    written_to: Path


def render_forecast_markdown(forecast: CashFlowForecast) -> str:
    """Rend le forecast en markdown commitable.

    Format simple : tableau 3 colonnes (fenêtre, montant attendu, n subs).
    Le founder lit ça dans son IDE — pas besoin de chartjs.
    """
    as_of_str = forecast.as_of.strftime("%Y-%m-%d")
    lines = [
        f"# Forecast cash flow — {as_of_str}",
        "",
        "> Généré par `InvoicePredictor`. Hypothèse : tout le portefeuille",
        "> actuel renouvelle à la prochaine échéance, pas de churn projeté.",
        "",
        "| Fenêtre | Rentrées attendues | ",
        "|---|---|",
        f"| J+30 | {forecast.expected_30d_eur} € |",
        f"| J+60 | {forecast.expected_60d_eur} € |",
        f"| J+90 | {forecast.expected_90d_eur} € |",
        "",
        f"- Subs considérées : **{forecast.n_subs_considered}**"
        f" (exclues : {forecast.n_subs_excluded} past_due / canceled / unpaid)",
        "",
    ]
    return "\n".join(lines)


def write_forecast(
    forecast: CashFlowForecast, *, target_dir: Path = DEFAULT_FORECAST_DIR
) -> Path:
    """Écrit le markdown et retourne le chemin du fichier généré."""
    target_dir.mkdir(parents=True, exist_ok=True)
    as_of_str = forecast.as_of.strftime("%Y-%m-%d")
    target = target_dir / f"forecast_{as_of_str}.md"
    target.write_text(render_forecast_markdown(forecast), encoding="utf-8")
    return target


class InvoicePredictor(BaseAgent):
    """Forecast cash flow 30/60/90j depuis les subs Stripe actives."""

    name = "InvoicePredictor"
    command = "/run-invoice-forecast"
    breaker_name = None
    ai_act_risk_class = "minimal"

    def __init__(self, *, target_dir: Path = DEFAULT_FORECAST_DIR) -> None:
        self._target_dir = target_dir

    async def run(self) -> RunResult:
        settings = get_settings()
        if settings.stripe_secret_key is None:
            raise ConfigError("STRIPE_SECRET_KEY manquant dans .env.local")

        try:
            subs: list[StripeSubscription] = await fetch_active_subscriptions(
                settings.stripe_secret_key
            )
        except Exception as exc:
            raise AgentDataSourceError(f"Stripe fetch: {exc}") from exc

        forecast = forecast_cash_flow(subs, as_of=datetime.now(UTC))
        try:
            target = write_forecast(forecast, target_dir=self._target_dir)
        except OSError as exc:
            raise AgentOutputError(f"write forecast: {exc}") from exc
        logger.info(f"InvoicePredictor — forecast écrit dans {target}")

        return RunResult(
            status="success",
            output_summary=forecast.summary(),
            extras={"written_to": str(target)},
        )


__all__ = [
    "DEFAULT_FORECAST_DIR",
    "InvoicePredictionRun",
    "InvoicePredictor",
    "render_forecast_markdown",
    "write_forecast",
]
