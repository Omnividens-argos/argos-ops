"""``InvoicePredictorScript`` — forecast cash flow (Finance, archi v2, S5).

Bras déterministe : calcule le forecast 30/60/90j depuis le snapshot des subs
(:func:`argos_ops.poles.finance.billing.forecast`), écrit le doc markdown
``docs/forecast_<date>.md`` (:func:`render_forecast_markdown`) et un fait
``kind="forecast"``. Pas de churn projeté (hypothèse : portefeuille stable).
"""

from __future__ import annotations

from pathlib import Path

from argos_ops.agents.invoice_predictor import render_forecast_markdown
from argos_ops.poles.base import BaseScript, ScriptResult
from argos_ops.poles.config import POLES_DIR
from argos_ops.poles.finance import billing
from argos_ops.poles.finance.docs import docs_dir


class InvoicePredictorScript(BaseScript):
    """Forecast cash flow 30/60/90j (``kind="forecast"`` + doc markdown)."""

    pole = "finance"
    name = "invoice_predictor"

    def __init__(self, *, poles_root: Path = POLES_DIR) -> None:
        super().__init__(poles_root=poles_root)

    async def run(self) -> ScriptResult:
        fc = billing.forecast(poles_root=self.poles_root)
        d = docs_dir(poles_root=self.poles_root)
        d.mkdir(parents=True, exist_ok=True)
        as_of = fc.as_of.strftime("%Y-%m-%d")
        (d / f"forecast_{as_of}.md").write_text(render_forecast_markdown(fc), encoding="utf-8")
        record = await self.write_memory(
            f"Forecast cash flow — J+30 {fc.expected_30d_eur} € · "
            f"J+60 {fc.expected_60d_eur} € · J+90 {fc.expected_90d_eur} € "
            f"({fc.n_subs_considered} sub(s) considérée(s))",
            kind="forecast",
            tags=("forecast", "cash"),
        )
        return ScriptResult(
            status="success",
            summary=fc.summary(),
            written=[record],
        )


__all__ = ["InvoicePredictorScript"]
