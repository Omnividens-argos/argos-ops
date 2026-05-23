---
description: Lance BotConfigManager — diff agent_config DB vs data/agent_config/baseline.yaml, alerte sur drifts
---

# /run-config-drift

Slash command Claude Code invoquée manuellement ou par Task Scheduler
(`argos-ops-config-drift`, quotidien) **sur l'ordi du fondateur** (D-017).

## Procédure

1. Lance `uv run python scripts/run_bot_config_manager.py` (foreground, ~1 sec).
2. Lis la sortie loguru et l'exit code.
3. **Si exit 0 et `output_summary` commence par `silence (vert)`** : aucun drift, baseline et DB en phase.
4. **Si exit 0 et `output_summary` commence par `alert pushed`** : un embed jaune (drift sur intensity/daily_limit) ou rouge (drift sur `enabled`) a été poussé. Propose au founder :
   - Si le drift est intentionnel et durable → update `data/agent_config/baseline.yaml` dans un commit dédié pour réabsorber le drift
   - Si le drift est un oubli → utiliser l'Admin Panel (`/api/agents/{name}` PATCH) ou SQL direct pour réaligner la DB sur la baseline
5. **Si exit 0 et `output_summary` commence par `alerte non envoyée`** : webhook absent.
6. **Si exit 1** : DB inaccessible.

## Notes

- Champs comparés : `enabled`, `intensity_level`, `daily_limit` (cf. `COMPARED_FIELDS` dans `argos_ops/agents/bot_config_manager.py`).
- `enabled=false` non baselined = critique (rouge) — un agent désactivé qui ne devrait pas l'être.
- Le report distingue `missing_in_db` (baseline déclare un agent mais aucune row en DB — agent jamais initialisé) et `missing_in_baseline` (row DB pour un agent non listé baseline — nouveau bot pas encore documenté).
