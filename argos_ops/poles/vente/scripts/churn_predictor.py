"""``ChurnPredictorScript`` — détection pré-churn par compte (Vente, archi v2, S4).

Bras déterministe : charge ``data/poles/vente/cs/customers.yaml`` et détecte les
signaux pré-churn (:func:`argos_ops.poles.vente.accounts.detect_churn`, heuristique
auditable RGPD § 22). Écrit un fait ``kind="churn"`` par compte à risque —
**important** si urgent (score ≥ 60). Les comptes sains ne génèrent aucun fait.
"""

from __future__ import annotations

from pathlib import Path

from argos_ops.poles.base import BaseScript, ScriptResult
from argos_ops.poles.config import POLES_DIR
from argos_ops.poles.vente import accounts
from argos_ops.poles.vente.accounts import URGENT_CHURN_THRESHOLD


class ChurnPredictorScript(BaseScript):
    """Mémorise les comptes à risque de churn (``kind="churn"``)."""

    pole = "vente"
    name = "churn_predictor"

    def __init__(self, *, poles_root: Path = POLES_DIR) -> None:
        super().__init__(poles_root=poles_root)

    async def run(self) -> ScriptResult:
        customers = accounts.load_accounts(poles_root=self.poles_root)
        signals = accounts.detect_churn(customers)
        if not signals:
            return ScriptResult(
                status="success",
                summary=f"{len(customers)} compte(s) analysé(s) — aucun signal de churn.",
                written=[],
            )

        written = []
        urgent = 0
        for s in signals:
            is_urgent = s.risk_score >= URGENT_CHURN_THRESHOLD
            if is_urgent:
                urgent += 1
            tags = ("urgent", "critical") if is_urgent else ("watch",)
            record = await self.write_memory(
                f"Churn {s.customer_id} — risque {s.risk_score}/100 : {'; '.join(s.signals)}",
                kind="churn",
                tags=tags,
                important=is_urgent,
                source=s.customer_id,
            )
            written.append(record)

        return ScriptResult(
            status="success",
            summary=f"{len(signals)} compte(s) à risque churn — {urgent} urgent(s) (≥ 60/100)",
            written=written,
        )


__all__ = ["ChurnPredictorScript"]
