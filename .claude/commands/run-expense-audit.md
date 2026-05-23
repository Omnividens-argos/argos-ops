---
description: Lance ExpenseAuditor — parse le dernier CSV Qonto et alerte sur anomalies (outliers / doublons / nouveaux vendors). Silence Discord si OK.
---

# /run-expense-audit

Slash command Claude Code invoquée manuellement ou par Task Scheduler
(`argos-ops-expense-audit`, mensuel après chaque export Qonto)
**sur l'ordi du fondateur** (D-017).

## Pré-requis

- Export CSV Qonto déposé dans `data/expenses/<YYYY-MM>.csv` (le bot pick le mtime-le-plus-récent).

## Procédure

1. Lance `uv run python scripts/run_expense_auditor.py` (foreground, ~1-2 s).
2. Lis la sortie loguru et l'exit code.
3. **Si exit 0 et `output_summary` commence par `silence (vert)`** : aucune anomalie (RAS).
4. **Si exit 0 et `output_summary` commence par `alert pushed`** : un embed jaune (juste `new_vendor`) ou rouge (`amount_outlier` ou `duplicate`) a été poussé sur `DISCORD_WEBHOOK_OPS_LOGS`. Propose au founder :
   - vérifier chaque anomalie listée
   - pour `new_vendor`, confirmer que c'est légitime (le vendor sera auto-ajouté au journal `data/expenses/vendors.md` ce run)
   - pour `duplicate` ou `amount_outlier`, examiner le relevé Qonto direct
5. **Si exit 0 et `output_summary` est `silence (aucun CSV)`** : aucun fichier dans `data/expenses/`. Demande au founder d'exporter depuis Qonto.

## Notes

- Les vendors connus sont mémorisés dans `data/expenses/vendors.md` (append-only, dedup au load). Pas de YAML pour limiter le diff bruyant.
- Le seuil outlier = 3× la médiane des débits du CSV (paramétrable côté code).
- Pas de connexion API Qonto (D-017 — aucun SaaS récurrent ajouté).

## Voir aussi

- Code : [argos_ops/agents/expense_auditor.py](../../argos_ops/agents/expense_auditor.py)
- Helper CSV : [argos_ops/finance/expense_csv.py](../../argos_ops/finance/expense_csv.py)