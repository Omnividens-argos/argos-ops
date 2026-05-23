---
description: Lance OrchestratorBot — décide quels bots de la fleet doivent tourner maintenant (dry-run par défaut, --live pour exécuter)
---

# /orchestrate

Slash command Claude Code pour piloter manuellement la fleet Argos Ops.
**Mode dry-run par défaut** : aucun agent n'est lancé tant que `--live`
n'est pas passé explicitement.

## Procédure

1. Si l'user a passé `--live` (ou demande explicitement « lance pour de vrai »), invoque
   `uv run python scripts/run_orchestrator.py --live` (avec `--max-concurrent N` si N a été précisé).
2. Sinon, invoque `uv run python scripts/run_orchestrator.py` (dry-run).
3. Lis la sortie loguru et l'exit code.
4. **Si exit 0** :
   - En dry-run : présente au founder le plan (agents `to_launch`, agents `skipped` avec leur raison) en 5-10 lignes max. Demande s'il veut switcher en `--live`.
   - En live : présente combien d'agents ont été lancés, combien ont réussi / échoué. Si un agent a échoué, lis l'erreur (loguru) et propose une piste.
5. **Si exit 1** : lis l'erreur loggée. Cause commune : container `argos-postgres-local` arrêté.

## Notes

- L'orchestrateur lit la cadence canonique de chaque bot dans `AGENT_FLEET` (`argos_ops/agents/orchestrator.py`). Quand un nouveau bot planifié rejoint la flotte, l'ajouter là.
- Verdicts possibles par agent : `launch`, `skipped_disabled`, `skipped_paused`, `skipped_daily_limit`, `skipped_breaker`, `skipped_not_due`, `skipped_intensity_zero`.
- Garde-fou parallélisme : `--max-concurrent 2` par défaut (cohérent avec le quota Claude Pro Max). En live, les agents sont lancés via `run_agent()` qui ré-applique le runtime guard P15/P16.B — donc même si un breaker trippe entre la planification et l'exécution, l'agent sera court-circuité proprement.
- Préparation P20/P21 : deux hooks `_consume_memory()` et `_consume_capabilities()` retournent `{}` aujourd'hui ; ils seront branchés sur Argos Memory et le Capabilities registry plus tard.
- Ne pas mettre `--live` en Task Scheduler tant que la chaîne n'a pas été éprouvée sur quelques runs manuels. La cadence cron est déjà couverte agent-par-agent (DigestBuilder cron 0 8, EmailBot */15 8-22, FinanceBot 0 6, BotHealthBot */2h) — l'orchestrateur live est utile en complément, pas en remplacement.
