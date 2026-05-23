---
description: Lance BotHealthBot — surveille uptime + erreurs récentes des bots actifs (silence Discord si tout vert)
---

# /run-bot-health

Slash command Claude Code invoquée toutes les 2 h par Task Scheduler
(`argos-ops-bot-health`) **sur l'ordi du fondateur** (cf. D-017).

## Procédure

1. Lance le script `uv run python scripts/run_bot_health.py` (foreground, ~2-3 secondes).
2. Lis la sortie loguru et l'exit code.
3. **Si exit 0 et `output_summary` commence par `silence (vert)`** :
   - Tout va bien, rien n'a été poussé sur Discord (politique anti-spam toutes les 2h).
   - Ne mentionne rien — silence est succès.
4. **Si exit 0 et `output_summary` commence par `alert pushed`** :
   - Un embed jaune (stale) ou rouge (error / breaker) a été poussé sur le webhook `DISCORD_WEBHOOK_OPS_LOGS`.
   - Lis le `summary` (ex : `2 ok · 1 stale · 0 error`) et propose au founder une piste si la cause est évidente (ex : Task Scheduler désactivé, container Postgres arrêté).
5. **Si exit 0 et `output_summary` commence par `alerte non envoyée`** :
   - Le webhook n'est pas configuré dans `.env.local`. Propose d'ajouter `DISCORD_WEBHOOK_OPS_LOGS`.
6. **Si exit 1 (failed)** :
   - Lis l'erreur loggée. Causes communes : container `argos-postgres-local` arrêté (`docker ps`), DB inaccessible.
   - Propose la correction, ne tente pas de fix automatique.

## Notes

- BotHealthBot **ne dépend pas de SupportBot** (agent interactif sans cadence cron) — seuls `DigestBuilder`, `EmailBot`, `FinanceBot` sont monitorés en Sprint 1. Quand un nouveau bot planifié rejoint la flotte, ajouter son nom + cadence dans `MONITORED_AGENTS` (`argos_ops/agents/bot_health.py`) et `DEFAULT_AGENT_MAX_AGE_HOURS` (`argos_ops/health.py`).
- L'agent logge déjà dans `agent_runs` — pas besoin de relogger.
- L'embed couleur :
  - Jaune : ≥ 1 agent stale (pas de run récent), pas d'erreur
  - Rouge : ≥ 1 erreur en 24 h, ou ≥ 1 breaker tripped
- Pour un diagnostic complet (DB + KB + queued + breakers + freshness), utilise plutôt `scripts/health_check.py` (cron quotidien 5h45).
