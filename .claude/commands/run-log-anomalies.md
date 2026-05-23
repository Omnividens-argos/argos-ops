---
description: Lance LogAnomalyDetector — détecte les pics d'erreurs sur agent_runs vs baseline 24h (silence Discord si normal)
---

# /run-log-anomalies

Slash command Claude Code invoquée manuellement ou par Task Scheduler
(``argos-ops-log-anomalies``, toutes les heures) **sur l'ordi du
fondateur** (D-017).

## Procédure

1. Lance ``uv run python scripts/run_log_anomaly.py`` (foreground, ~1 sec).
2. Lis la sortie loguru et l'exit code.
3. **Si exit 0 et ``output_summary`` commence par ``silence (vert)``** : le
   volume d'erreurs sur la dernière heure est normal ou sous le bruit
   de fond. Rien à faire.
4. **Si exit 0 et ``output_summary`` commence par ``alert pushed``** : un
   embed jaune (ratio ≥3x baseline) ou rouge (ratio ≥5x ou ≥50
   absolu) a été poussé. Lis le summary :
   - **Ratio ≥3x baseline + volume modéré** : un agent commence à
     dériver. Check le top agents listé, regarde ``agent_runs`` brut
     pour la signature dominante.
   - **Volume ≥50/h ou ratio ≥5x** : suspecter une boucle de retry
     infinie ou un service externe down (Stripe API, OVH Zimbra,
     OSV.dev). Vérifier si un breaker est tripped (``/reset-breaker``
     sans argument liste les actifs).
5. **Si exit 1** : erreur DB (connexion Postgres). Vérifier que le
   container ``argos-postgres-local`` tourne.

## Notes

- Complémentaire de ``/run-error-triage`` qui clusterise les erreurs
  par signature. Si les deux alertes partent ensemble, le triage donne
  la cause (« quelle erreur ») et anomaly donne l'urgence (« à quel
  rythme »).
- Le baseline = moyenne horaire des 24 h précédant la dernière heure.
  Au-dessous de ``BASELINE_FLOOR=1.0``, on assume 1/h pour éviter qu'un
  baseline à 0 ne fasse exploser le ratio.
- Pas de breaker associé — c'est un capteur passif, pas un actionneur.
