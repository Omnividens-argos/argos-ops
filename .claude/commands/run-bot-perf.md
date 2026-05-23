---
description: Lance BotPerfAnalyzer — durée P50/P95 + taux d'erreur 7j par bot, alerte si dérive >= 1.5x baseline (silence Discord sinon)
---

# /run-bot-perf

Slash command Claude Code invoquée manuellement ou par Task Scheduler
(`argos-ops-bot-perf`, hebdomadaire) **sur l'ordi du fondateur** (D-017).

## Procédure

1. Lance `uv run python scripts/run_bot_perf.py` (foreground, ~3-5 secondes).
2. Lis la sortie loguru et l'exit code.
3. **Si exit 0 et `output_summary` commence par `silence (vert)`** : tout est stable, rien poussé sur Discord (anti-spam hebdomadaire).
4. **Si exit 0 et `output_summary` commence par `alert pushed`** : un embed jaune (warn 1.5-2x baseline) ou rouge (regression ≥ 2x) a été poussé sur `DISCORD_WEBHOOK_OPS_LOGS`. Lis le summary (ex : `2 ok · 1 warn · 0 regression`) et propose au founder une piste si évidente (ex : EmailBot ralenti = peut-être migration OVH, FinanceBot lent = Stripe API timeout).
5. **Si exit 0 et `output_summary` commence par `alerte non envoyée`** : webhook `DISCORD_WEBHOOK_OPS_LOGS` absent dans `.env.local`.
6. **Si exit 1** : lis l'erreur. Causes communes : container `argos-postgres-local` arrêté.

## Notes

- Fenêtre courante : 7 derniers jours. Baseline : J-14 → J-7. En deçà de 5 samples sur l'une des fenêtres → classé `ok` avec raison "insufficient samples" (anti faux positif sur agent qui démarre).
- Agents monitorés = ceux de `MONITORED_AGENTS` dans `argos_ops/agents/bot_health.py` (DigestBuilder, EmailBot, FinanceBot par défaut). Quand un nouveau bot planifié rejoint la flotte, ajouter son nom dans cette tuple suffit — les deux watchers le picorent.
- Pour analyser un bot individuellement, lire `agent_runs` direct via `scripts/query_agent.py` (à venir Sprint 3) ou SQL `SELECT * FROM agent_runs WHERE agent_name='X' ORDER BY started_at DESC LIMIT 50`.
