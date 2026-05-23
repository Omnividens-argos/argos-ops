---
description: Lance DealRiskScorer — score chaque deal du pipe + flag les stalled (> seuil par stade). Read-only, alerte Discord top 3 risque.
---

# /run-deal-scoring

Slash command Claude Code invoquée manuellement ou par Task Scheduler (`argos-ops-deal-scoring`, cadence quotidienne 8h Paris, après le digest) **sur l'ordi du fondateur** (D-017).

## Procédure

1. Lance `uv run python scripts/run_deal_risk_scorer.py`.
2. **Si exit 0 et `silence (no deals)`** : `data/sales/deals/pipe.yaml` absent. Le founder doit créer son pipe à la main.
3. **Si exit 0 et `stalled > 0`** : Discord embed orange poussé avec top 3. Propose au founder de relancer prioritairement les deals stalled (mail / call).
4. **Si exit 0 et `stalled=0`** : pipe propre, pas d'action.

## Notes

- Format `data/sales/deals/pipe.yaml` :
  ```yaml
  deals:
    - deal_id: "acme-q2-2026"
      company: "Acme SA"
      stage: "demo_done"  # discovery|demo_scheduled|demo_done|proposal_sent|contract_sent|won|lost
      amount_eur: 4200
      last_activity_at: 2026-05-10
      owner: "founder"
      notes: "Marc revient mardi avec son board"
  ```
- Seuils stalled par stade (cf. `argos_ops.sales.scoring.STALLED_THRESHOLD_DAYS`) :
  - discovery / demo_done / proposal_sent : 14 jours
  - demo_scheduled : 7 jours (créneau planifié sans suivi = très chaud)
  - contract_sent : 30 jours (signature légale = patience)
- Risk score 0-100 combine inactivité, montant et avancement dans le pipe.
- Read-only — ne touche jamais le YAML. Breaker associé : `DealRiskScorer` (P15).
