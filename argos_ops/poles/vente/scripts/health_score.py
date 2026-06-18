"""``HealthScoreScript`` — score santé par compte (Vente, archi v2, S4).

Bras déterministe : charge ``data/poles/vente/cs/customers.yaml`` et calcule un
score santé 0-100 + bande (:func:`argos_ops.poles.vente.accounts.score_health`,
heuristique auditable RGPD § 22). Écrit un fait ``kind="health"`` pour les comptes
**non verts** (jaune/rouge) — important si rouge. Les comptes verts sont du bruit :
non mémorisés, juste comptés.
"""

from __future__ import annotations

from pathlib import Path

from argos_ops.cs.models import HealthBand
from argos_ops.poles.base import BaseScript, ScriptResult
from argos_ops.poles.config import POLES_DIR
from argos_ops.poles.vente import accounts


class HealthScoreScript(BaseScript):
    """Mémorise les comptes jaune/rouge (``kind="health"``)."""

    pole = "vente"
    name = "health_score"

    def __init__(self, *, poles_root: Path = POLES_DIR) -> None:
        super().__init__(poles_root=poles_root)

    async def run(self) -> ScriptResult:
        customers = accounts.load_accounts(poles_root=self.poles_root)
        scores = accounts.score_health(customers)
        if not scores:
            return ScriptResult(
                status="success",
                summary="Aucun compte (data/poles/vente/cs/customers.yaml) — rien à scorer.",
                written=[],
            )

        written = []
        red = 0
        green = 0
        for h in scores:
            if h.band == HealthBand.GREEN:
                green += 1
                continue  # vert = sain, non mémorisé (bruit)
            is_red = h.band == HealthBand.RED
            if is_red:
                red += 1
            tags = (h.band.value, "critical") if is_red else (h.band.value,)
            record = await self.write_memory(
                f"Santé {h.customer_id} — {h.score}/100 ({h.band.value}) : {'; '.join(h.drivers)}",
                kind="health",
                tags=tags,
                important=is_red,
                source=h.customer_id,
            )
            written.append(record)

        return ScriptResult(
            status="success",
            summary=f"{len(scores)} compte(s) scoré(s) — {green} vert(s), {red} rouge(s)",
            written=written,
        )


__all__ = ["HealthScoreScript"]
