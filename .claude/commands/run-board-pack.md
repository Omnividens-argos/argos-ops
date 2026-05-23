---
description: Lance BoardReporter — board pack mensuel pandoc-ready (MRR / burn / runway / NRR / opérations)
---

# /run-board-pack

## Procédure

1. Lance `uv run python scripts/run_board_reporter.py`.
2. Le bot :
   - Calcule MRR via `sum_active_mrr_eur` (FinanceBot source de vérité)
   - Lit `data/strategy/burn.yaml` pour burn + runway si disponible
   - Compte les agent runs du mois + breakers tripped + incidents
   - Écrit `data/strategy/board-YYYY-MM.md`
3. Pour générer le PDF :

```bash
pandoc data/strategy/board-2026-05.md -o data/strategy/board-2026-05.pdf --pdf-engine=xelatex
```

## Notes

- Cadence cible : 1er du mois pour le mois précédent
- Pas de push Discord (board pack reste interne)
- Skill réutilisé : `stripe-ops` via FinanceBot (cohérence chiffres)
- NRR placeholder tant qu'on n'a pas assez de cohortes (≥ 6 mois d'historique)
