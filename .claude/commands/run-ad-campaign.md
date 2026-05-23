---
description: Lance AdBot live (P12.B) — applique les recommandations chiffrées d'ads-optimizer sur Google / LinkedIn / Meta Ads. Shadow tant que ADS_LIVE_MODE=false (D-026).
---

# /run-ad-campaign

Slash command pour AdBot live (P12.B). Lit les recos YAML produites par
le skill `ads-optimizer` sous `data/ads/recommendations/`, applique les
actions en respectant le cap `ADS_DAILY_BUDGET_EUR`, archive le tout
dans `data/ads/applied/`.

## Préconditions

- Au moins un fichier YAML dans `data/ads/recommendations/`
- `ADS_LIVE_MODE=true` + `ADS_DAILY_BUDGET_EUR > 0` pour le mode live
- Breaker `ad_spend_runaway` non tripped

## Procédure

```python
from argos_ops.agents.base import run_agent
from argos_ops.agents.ad_bot_live import AdBotLive

result = await run_agent(AdBotLive())
print(result.status, result.output_summary)
```

## Sortie attendue

`output_summary="recos=N applied=K shadow=M blocked=0 €/week=+XX"` +
notif Discord avec budget engagé.

## Garde-fous

- Cap budget : si |delta|/7 d'une reco dépasse le budget jour, AdBot
  archive avec `status: blocked_budget_cap`
- D-026 conditionne le passage en live au validation founder d'un
  budget pub mensuel > 0 € + backtest 4 semaines de CSV shadow
  produits via `/analyze-ads`
