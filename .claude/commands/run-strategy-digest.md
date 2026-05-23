---
description: Lance StrategyBot — digest hebdomadaire KPIs agents (Discord + markdown)
---

# /run-strategy-digest

## Procédure

1. Lance `uv run python scripts/run_strategy_bot.py`.
2. Le bot :
   - Lit `agent_runs` sur les 7 derniers jours
   - Aggrège par agent (total / success / failed / skipped)
   - Écrit `data/strategy/digest-YYYY-WW.md`
   - Push un Embed Discord sur `DISCORD_WEBHOOK_OPS_LOGS`
3. Lis le markdown produit et complète la section « TODO fondateur »
   si besoin.

## Notes

- Cadence cible : lundi matin (rendez-vous hebdo)
- Pas de silence Discord : c'est un push systématique (rendez-vous fondateur)
- Si webhook absent : warn loguru, pas d'erreur fatale
