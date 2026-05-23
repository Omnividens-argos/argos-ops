---
description: Lance ChurnPredictor — détecte les signaux pré-churn par compte, score 0-100. Snapshot YAML + Discord rouge si urgent (score ≥ 60).
---

# /run-churn-predict

Slash command Claude Code invoquée manuellement ou par Task Scheduler (`argos-ops-churn`, quotidien 9h30 Paris, après le digest et HealthScoreBot).

## Procédure

1. Lance `uv run python scripts/run_churn_predictor.py`.
2. **Si `silence (no customers)`** : pas de CRM CS.
3. **Si `urgent > 0`** : Discord rouge → appel proactif sous 48h. Lis `data/churn/at_risk_<date>.yaml`.
4. **Si `at_risk > 0` mais aucun urgent** : Discord jaune (à surveiller, pas de panique).
5. **Si tout vert** : silence Discord.

## Notes

- Signaux cumulatifs (cf. `argos_ops/cs/scoring.py`) :
  - inactivité ≥ 30j : +35 pts
  - NPS détracteur (≤ 6) : +30 pts
  - tickets 30j ≥ 6 : +25 pts
  - sous-utilisation (< 10% du quota) : +15 pts
- Seuil urgent : `URGENT_RISK_THRESHOLD = 60` (action 48h).
- Read-only. Le snapshot du jour est écrasé à chaque run.
- Complémentaire à `/run-health-scores` : HealthScore = état général, ChurnPredictor = trajectoire vers la sortie.
- Breaker : `ChurnPredictor` (P15).
