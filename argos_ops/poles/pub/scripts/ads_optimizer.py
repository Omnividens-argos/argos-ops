"""``AdsOptimizerScript`` — CSV de campagnes → recos chiffrées (Pub, archi v2, S3).

Bras déterministe du pôle Pub :

1. lit le dernier export CSV **par plateforme** sous
   ``data/poles/pub/campaigns/`` (:func:`~argos_ops.poles.pub.optimizer.load_latest_campaigns`) ;
2. calcule CTR/CPC/CPA et produit jusqu'à 5 **recommandations chiffrées**
   (€/semaine) via :func:`~argos_ops.poles.pub.optimizer.recommend` ;
3. met à jour la **jauge de budget** et **arme le breaker** ``ad_spend_runaway``
   si la dépense moyenne/jour dépasse le seuil (:mod:`~argos_ops.poles.pub.budget`) ;
4. écrit un fait par reco dans **sa propre mémoire** (``kind="ad_reco"``, l'action
   et la plateforme en tags pour que :class:`PubAgent` les relise), plus un fait
   de synthèse budget si le breaker s'arme.

Pas de Discord, pas de DB, pas de LLM (D-017) : le :class:`PubAgent` lit cette
mémoire et planifie. Idempotent : même CSV ⇒ mêmes recos / même état / mêmes faits.
"""

from __future__ import annotations

from pathlib import Path

from argos_ops.poles.base import BaseScript, ScriptResult
from argos_ops.poles.config import POLES_DIR
from argos_ops.poles.pub import budget, optimizer
from argos_ops.poles.pub.optimizer import AdRecommendation

_DEFAULT_WINDOW_DAYS = 7


class AdsOptimizerScript(BaseScript):
    """Analyse les exports CSV et mémorise des recos chiffrées (``kind="ad_reco"``)."""

    pole = "pub"
    name = "ads_optimizer"

    def __init__(
        self,
        *,
        poles_root: Path = POLES_DIR,
        cpa_target_eur: float = 80.0,
        window_days: int = _DEFAULT_WINDOW_DAYS,
    ) -> None:
        super().__init__(poles_root=poles_root)
        self._cpa_target_eur = cpa_target_eur
        self._window_days = window_days

    def _severity_for(self, reco: AdRecommendation) -> bool:
        """Un fait reco est ``important`` ssi il est critique (pause)."""
        return reco.severity == "critical"

    async def run(self) -> ScriptResult:
        rows_by_platform = optimizer.load_latest_campaigns(poles_root=self.poles_root)
        if not rows_by_platform:
            return ScriptResult(
                status="success",
                summary="Aucun export de campagne (data/poles/pub/campaigns/) — rien à optimiser.",
                written=[],
            )

        # 2-3. Recos + mise à jour jauge/breaker (la dépense pilote l'armement).
        recos = optimizer.recommend(
            rows_by_platform,
            cpa_target_eur=self._cpa_target_eur,
            window_days=self._window_days,
        )
        spend = optimizer.spend_by_platform(rows_by_platform)
        state = budget.update_spend(
            spend, window_days=self._window_days, poles_root=self.poles_root
        )

        # 4. Un fait par reco (action + plateforme en tags pour le PubAgent).
        written = []
        for reco in recos:
            tags: tuple[str, ...] = (reco.action, reco.platform, reco.severity)
            if reco.severity == "critical":
                tags = (*tags, "critical")
            record = await self.write_memory(
                f"[{reco.platform}] {reco.campaign} — {reco.rationale}",
                kind="ad_reco",
                tags=tags,
                important=self._severity_for(reco),
                source=reco.platform,
            )
            written.append(record)

        # Fait de synthèse budget si le breaker est armé (signal fort pour l'agent).
        if state.breaker_tripped:
            record = await self.write_memory(
                f"Breaker ad_spend_runaway ARMÉ — {state.breaker_reason}",
                kind="budget_alert",
                tags=("ad_spend_runaway", "critical"),
                important=True,
            )
            written.append(record)

        return ScriptResult(
            status="success",
            summary=(
                f"{len(recos)} reco(s) sur {sum(len(r) for r in rows_by_platform.values())} "
                f"campagne(s) — dépense {state.spent_per_day_eur:.0f} €/j"
                + (" — BREAKER ARMÉ" if state.breaker_tripped else "")
            ),
            written=written,
        )


__all__ = ["AdsOptimizerScript"]
