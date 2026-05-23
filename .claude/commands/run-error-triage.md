---
description: Lance ErrorTriageBot — regroupe les erreurs 24h par signature, alerte si ≥ 3 occurrences (silence sinon)
---

# /run-error-triage

Slash command Claude Code invoquée manuellement ou par Task Scheduler
(`argos-ops-error-triage`, toutes les 6h) **sur l'ordi du fondateur** (D-017).

## Procédure

1. Lance `uv run python scripts/run_error_triage.py` (foreground, ~1-2 sec).
2. Lis la sortie loguru et l'exit code.
3. **Si exit 0 et `output_summary` commence par `silence (vert)`** : aucun cluster ≥ 3 occurrences, tout va bien.
4. **Si exit 0 et `output_summary` commence par `alert pushed`** : un embed jaune (cluster 3-9) ou rouge (cluster ≥10 = probable crise) a été poussé. Lis le summary (ex : `2 cluster(s) >= 3 · 17 erreur(s) totale(s) sur 24h`). Propose au founder une investigation : regarder `agent_runs.error` filtrés sur la signature pour trouver la cause racine.
5. **Si exit 0 et `output_summary` commence par `alerte non envoyée`** : webhook absent.
6. **Si exit 1** : DB inaccessible.

## Notes

- Signature = première séquence de mots / type d'exception extrait du message d'erreur (ex : `ConnectionError`, `TimeoutError`, `ValueError`).
- Les clusters à 1-2 occurrences sont du bruit (réseau intermittent, OVH qui hoquette) — masqués volontairement.
- Pour rappel : `agent_runs.error` est rempli automatiquement par `run_agent` quand un agent crash. Format toujours `"ExcType: message"`.
