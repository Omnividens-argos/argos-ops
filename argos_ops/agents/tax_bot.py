"""TaxBot — Fiscaliste (Sprint 10).

Pré-prépare une déclaration TVA CA3 mensuelle + une estimation IS
prévisionnel et les écrit dans ``data/finance/ca3_<YYYY-MM>.md``.

Hypothèses (cf. ``argos_ops.finance.tva``) :
- TVA normale 20 % sur prestations SaaS BtoB France.
- CA HT estimé = MRR Stripe courant (proxy : pas de réelle facturation
  historique exposée par notre intégration P7).
- IS PME : 15 % jusqu'à 42 500 €, 25 % au-delà.

**Aucune publication DGFiP** — c'est un draft destiné à être audité
par le founder (ou son comptable) avant dépôt sur impots.gouv.fr le
19 du mois M+1.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from loguru import logger

from argos_ops.agents.base import BaseAgent, RunResult
from argos_ops.config import REPO_ROOT, get_settings
from argos_ops.exceptions import AgentDataSourceError, AgentOutputError, ConfigError
from argos_ops.finance.tva import (
    CA3Report,
    ISForecast,
    compute_ca3,
    estimate_is,
)
from argos_ops.integrations.stripe_client import (
    compute_mrr_eur,
    fetch_active_subscriptions,
)

DEFAULT_TARGET_DIR: Path = REPO_ROOT / "data" / "finance"


@dataclass(frozen=True)
class TaxRun:
    """Bilan d'un run TaxBot."""

    ca3: CA3Report
    is_forecast: ISForecast | None
    written_to: Path


def render_tax_markdown(ca3: CA3Report, is_forecast: ISForecast | None) -> str:
    """Format markdown commitable du draft fiscal."""
    lines = [
        f"# Déclaration TVA CA3 — {ca3.period_month} (draft)",
        "",
        "> Généré par `TaxBot`. À auditer avant dépôt sur impots.gouv.fr",
        "> (date limite : le 19 du mois M+1).",
        "",
        "## Champs CA3 principaux",
        "",
        "| Ligne | Montant |",
        "|---|---|",
        f"| Base HT (prestations services 20%) | {ca3.ca_ht_eur} € |",
        f"| TVA collectée | {ca3.tva_collected_eur} € |",
        f"| TVA déductible (sur achats) | {ca3.tva_deductible_eur} € |",
        f"| **TVA nette due** | **{ca3.tva_net_due_eur} €** |",
        "",
        "## Méthode d'estimation",
        "",
        "- CA HT estimé = MRR Stripe courant x 1 mois (proxy).",
        "- TVA collectée = CA HT x 20 % (taux normal, services BtoB FR).",
        "- TVA déductible = 0 par défaut. À renseigner manuellement avec les",
        "  factures fournisseurs (Qonto export → onglet débits).",
        "",
    ]
    if is_forecast is not None:
        lines.extend(
            [
                "## IS prévisionnel (annuel)",
                "",
                f"- Résultat avant impôt estimé : **{is_forecast.profit_before_tax_eur} €**",
                f"- IS taux réduit 15 % (≤ 42 500 €) : {is_forecast.is_reduced_part_eur} €",
                f"- IS taux normal 25 % (au-delà) : {is_forecast.is_normal_part_eur} €",
                f"- **IS total estimé : {is_forecast.is_total_eur} €**",
                "",
            ]
        )
    return "\n".join(lines)


def write_tax_draft(
    ca3: CA3Report,
    is_forecast: ISForecast | None,
    *,
    target_dir: Path = DEFAULT_TARGET_DIR,
) -> Path:
    """Écrit le draft markdown et retourne le chemin du fichier."""
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"ca3_{ca3.period_month}.md"
    target.write_text(render_tax_markdown(ca3, is_forecast), encoding="utf-8")
    return target


class TaxBot(BaseAgent):
    """Fiscaliste — drafte la TVA CA3 mensuelle + IS prévisionnel."""

    name = "TaxBot"
    command = "/run-tax-prep"
    breaker_name = None
    ai_act_risk_class = "minimal"

    def __init__(
        self,
        *,
        target_dir: Path = DEFAULT_TARGET_DIR,
        projected_annual_profit_eur: Decimal | None = None,
    ) -> None:
        self._target_dir = target_dir
        self._projected_profit = projected_annual_profit_eur

    async def run(self) -> RunResult:
        settings = get_settings()
        if settings.stripe_secret_key is None:
            raise ConfigError("STRIPE_SECRET_KEY manquant dans .env.local")

        try:
            subs = await fetch_active_subscriptions(settings.stripe_secret_key)
        except Exception as exc:
            raise AgentDataSourceError(f"Stripe fetch: {exc}") from exc

        mrr = compute_mrr_eur(subs)
        now = datetime.now(UTC)
        period_month = now.strftime("%Y-%m")

        ca3 = compute_ca3(period_month=period_month, ca_ht_eur=mrr)
        is_forecast = (
            estimate_is(self._projected_profit) if self._projected_profit is not None else None
        )
        try:
            target = write_tax_draft(ca3, is_forecast, target_dir=self._target_dir)
        except OSError as exc:
            raise AgentOutputError(f"write tax draft: {exc}") from exc
        logger.info(f"TaxBot — CA3 draft écrit dans {target}")

        return RunResult(
            status="success",
            output_summary=ca3.summary(),
            extras={"written_to": str(target)},
        )


__all__ = [
    "DEFAULT_TARGET_DIR",
    "TaxBot",
    "TaxRun",
    "render_tax_markdown",
    "write_tax_draft",
]
