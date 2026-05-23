---
description: Lance HealthScoreBot — score santé 0-100 par client (usage + tickets + NPS + inactivité). Snapshot YAML quotidien. Discord si jaune/rouge.
---

# /run-health-scores

Slash command Claude Code invoquée manuellement ou par Task Scheduler (`argos-ops-health-scores`, quotidien 9h Paris).

## Procédure

1. Lance `uv run python scripts/run_health_score.py`.
2. **Si exit 0 et `silence (no customers)`** : `data/cs/customers.yaml` absent.
3. **Si exit 0 et bande rouge ou jaune** : embed Discord posté avec top 3 à risque. Founder examine `data/health_scores/snapshot_<date>.yaml` (drivers détaillés).
4. **Si tout vert** : silence Discord, snapshot écrit quand même pour historique.

## Notes

- Score 0-100 (cf. `argos_ops/cs/scoring.py`) :
  - usage (40 pts) — sous-utilisation ET saturation pénalisent
  - tickets 30j (20 pts)
  - NPS (20 pts)
  - inactivité (20 pts)
- Bandes :
  - vert ≥ 70 (sain)
  - jaune 40-69 (à surveiller)
  - rouge < 40 (pré-churn — voir aussi `/run-churn-predict`)
- Snapshot écrasé chaque jour — pour comparer dans le temps, archiver
  manuellement ou attendre P22.J historisation.
- Read-only sur `data/cs/customers.yaml` — ne modifie pas le CRM.
- Breaker associé : `HealthScoreBot` (P15).
