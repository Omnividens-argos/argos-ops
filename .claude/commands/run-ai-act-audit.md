---
description: Lance AIActComplianceBot — vérifie le tag ai_act_risk_class de chaque agent
---

# /run-ai-act-audit

Slash Claude Code invoquée manuellement ou par Task Scheduler.

## Procédure

1. Lance `uv run python scripts/run_ai_act_compliance.py`.
2. Lis l'exit code et `output_summary`.
3. **Si `silence (vert)`** : tous les agents ont un `ai_act_risk_class` valide.
4. **Si `alert pushed` (YELLOW)** : ≥1 agent `unclassified`.
   - Ajouter `ai_act_risk_class = "minimal" | "limited" | "high" | "prohibited"`
     sur la classe agent fautive
5. **Si `alert pushed` (RED)** : ≥1 agent tagué `prohibited` — incompatible avec
   l'AI Act art. 5. Soit retirer l'agent, soit reclasser après revue légale.

## Notes

- Source de vérité : attribut `ai_act_risk_class` sur la classe agent
- Catégories canoniques :
  - `minimal` — pas de risque (watchers passifs, agents purement déterministes)
  - `limited` — IA générative, transparence obligatoire (AI Act art. 50)
  - `high` — décisions à impact significatif (interdites en mode auto pour Argos)
  - `prohibited` — interdit par l'AI Act art. 5
