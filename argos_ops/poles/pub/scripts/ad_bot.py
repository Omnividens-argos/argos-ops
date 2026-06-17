"""``AdBotScript`` — pousseur **shadow** de campagnes (Pub, archi v2, S3).

Bras déterministe du pôle Pub, **mode shadow par défaut** (D-026 : aucun appel
plateforme tant que le mode live n'est pas armé). Il matérialise ce qu'il
*pousserait* en live :

1. les **créas validées** (:func:`~argos_ops.poles.pub.creatives.find_publishable`)
   → une action shadow ``publish`` par créa ;
2. les **recos appliquées** (:mod:`~argos_ops.poles.pub.applied`) → une action
   shadow reflétant l'action de la reco (pause / scale / …).

**Garde-fou breaker** : si ``ad_spend_runaway`` est armé, toute action
augmentatrice de dépense (lancer une créa, scaler) est **bloquée** et tracée
comme telle — jamais exécutée, même en shadow. Écrit sa mémoire
(``kind="ad_action"``) ; pas de Discord, pas de DB, pas de LLM (D-017).
Idempotent : même entrée ⇒ mêmes faits (hash du corps).
"""

from __future__ import annotations

from argos_ops.poles.base import BaseScript, ScriptResult
from argos_ops.poles.memory import MemoryRecord
from argos_ops.poles.pub import applied, budget, creatives
from argos_ops.poles.pub.optimizer import SPEND_INCREASING

# Lancer une créa engage de la dépense → bridé comme une action augmentatrice.
_PUBLISH_ACTION = "publish"


class AdBotScript(BaseScript):
    """Pousse (shadow) créas validées + recos appliquées, borné par le breaker."""

    pole = "pub"
    name = "ad_bot"

    async def run(self) -> ScriptResult:
        state = budget.load_budget(poles_root=self.poles_root)
        tripped = state.breaker_tripped
        written: list[MemoryRecord] = []
        blocked = 0

        # 1. Créas validées → publication shadow (bloquée si breaker armé).
        for creative in creatives.find_publishable(poles_root=self.poles_root):
            is_blocked = tripped  # publier = engager de la dépense
            blocked += int(is_blocked)
            verb = "BLOQUÉ (breaker armé)" if is_blocked else "publierait (shadow)"
            record = await self.write_memory(
                f"AdBot {verb} : créa « {creative.title} » sur {creative.platform}",
                kind="ad_action",
                tags=(creative.platform, _PUBLISH_ACTION, "blocked" if is_blocked else "shadow"),
                important=is_blocked,
                source=creative.id,
            )
            written.append(record)

        # 2. Recos appliquées → action shadow (les augmentatrices bloquées si armé).
        for reco in applied.load_applied(poles_root=self.poles_root):
            is_blocked = tripped and reco.action in SPEND_INCREASING
            blocked += int(is_blocked)
            verb = "BLOQUÉ (breaker armé)" if is_blocked else "appliquerait (shadow)"
            record = await self.write_memory(
                f"AdBot {verb} : {reco.action} sur {reco.platform} / {reco.campaign} "
                f"({reco.eur_delta_week:+.0f} €/sem)",
                kind="ad_action",
                tags=(reco.platform, reco.action, "blocked" if is_blocked else "shadow"),
                important=is_blocked,
                source=reco.id,
            )
            written.append(record)

        if not written:
            return ScriptResult(
                status="success",
                summary="Aucune créa validée ni reco appliquée — rien à pousser (shadow).",
                written=[],
            )
        return ScriptResult(
            status="success",
            summary=(
                f"{len(written)} action(s) shadow — {blocked} bloquée(s) par le breaker"
                if tripped
                else f"{len(written)} action(s) shadow (breaker OK)"
            ),
            written=written,
        )


__all__ = ["AdBotScript"]
