---
description: Lance OKRTracker — compare la progression des OKRs trimestriels vs prorata temporis
---

# /run-okr-review

## Procédure

1. Lance `uv run python scripts/run_okr_tracker.py`.
2. Le bot lit `data/okr/YYYY-Qn.yaml` (déduit du trimestre courant).
3. **Si `silence (vert)`** : tous les KRs sont on_track.
4. **Si `alert pushed` (YELLOW)** : ≥1 KR at_risk (progrès 50-90% du prorata).
5. **Si `alert pushed` (RED)** : ≥1 KR off_track (progrès < 50%) ou fichier absent.

## Format YAML attendu

```yaml
quarter: '2026-Q2'
year: 2026
quarter_num: 2
objectives:
  - title: 'Atteindre 10k€ MRR'
    key_results:
      - name: 'MRR fin Q2'
        target: 10000
        actual: 4500
        unit: EUR
```

## Notes

- Prorata temporis : on tolère un délai de < 5% au début du trimestre
- Cadence cible : bi-mensuelle (mi-mois + fin de mois)
- Les `actual` sont à mettre à jour manuellement par le fondateur — les bots
  Direction n'écrivent pas dans le YAML (séparation source de vérité)
