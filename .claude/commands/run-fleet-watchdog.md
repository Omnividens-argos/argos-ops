---
description: Lance FleetWatchdog — SRE unifié de la flotte (santé + perf + triage erreurs + anomalies en 1 passe sur agent_runs, silence Discord si tout vert)
---

# /run-fleet-watchdog

Slash command Claude Code invoquée **toutes les 6 h** par Task Scheduler
(`argos-ops-fleet-watchdog`) **sur l'ordi du fondateur** (cf. D-017).

FleetWatchdog (Axe 3.2, [D-031](../../docs/DECISIONS.md)) **fusionne les 4 anciens
watchers** qui lisaient tous `agent_runs` (`BotHealthBot` + `BotPerfAnalyzer` +
`ErrorTriageBot` + `LogAnomalyDetector`) : 1 session DB, 4 sous-sections,
**1 embed Discord multi-sections** au lieu de 4. Remplace
`/run-bot-health`, `/run-bot-perf`, `/run-error-triage`, `/run-log-anomalies`.

## Procédure

1. Lance `uv run python scripts/run_fleet_watchdog.py` (foreground, ~3-5 secondes).
2. Lis la sortie loguru et l'exit code.
3. **Si exit 0 et `output_summary` commence par `silence (vert)`** :
   - Les 4 sections sont vertes, rien n'a été poussé sur Discord (anti-spam).
   - Ne mentionne rien — silence est succès.
4. **Si exit 0 et `output_summary` commence par `alert pushed`** :
   - Un embed jaune ou rouge a été poussé sur `DISCORD_WEBHOOK_OPS_LOGS`. Le
     `summary` indique le statut par section
     (ex : `santé [GREEN] · perf [GREEN] · erreurs [YELLOW] · anomalie [GREEN]`).
   - Seules les sections **en alerte** sont dépliées dans l'embed. Propose une
     piste au founder selon la section rouge/jaune :
     - **santé** → un agent stale (Task Scheduler désactivé ?) ou en erreur, ou un breaker tripped (`/reset-breaker`).
     - **perf** → un agent a une latence P95 ou un taux d'erreur ≥1.5x (jaune) / ≥2x (rouge) la baseline 7 j.
     - **erreurs** → une signature d'exception revient ≥3 fois (jaune) / ≥10 fois (rouge) en 24 h.
     - **anomalie** → pic de volume d'erreurs sur la dernière heure (≥3x baseline = jaune, ≥5x ou ≥50 absolu = rouge) ; vérifie le top agents.
5. **Si exit 0 et `output_summary` commence par `alerte non envoyée`** :
   - Le webhook n'est pas configuré dans `.env.local`. Propose d'ajouter `DISCORD_WEBHOOK_OPS_LOGS`.
6. **Si exit 1 (failed)** :
   - Lis l'erreur loggée. Cause commune : container `argos-postgres-local` arrêté (`docker ps`), DB inaccessible.
   - Propose la correction, ne tente pas de fix automatique.

## Notes

- **Couleur globale = la plus sévère des 4 sections** (RED > YELLOW > GREEN) ;
  `should_alert` = OR des 4. Silence si les 4 sont vertes.
- Agents surveillés par la section *santé* = `MONITORED_AGENTS`
  (`DigestBuilder`, `EmailBot`, `FinanceBot`). Pour en ajouter : éditer
  `MONITORED_AGENTS` dans `argos_ops/agents/_watchdog/health.py` **et**
  `DEFAULT_AGENT_MAX_AGE_HOURS` dans `argos_ops/health.py`.
- FleetWatchdog se logge lui-même dans `agent_runs` et est surveillé par
  `scripts/health_check.py` (freshness, seuil 7 h) — il ne s'auto-surveille pas.
- Pour un diagnostic complet (DB + KB + queued + breakers + freshness), utilise
  plutôt `scripts/health_check.py` (cron quotidien 5h45).
