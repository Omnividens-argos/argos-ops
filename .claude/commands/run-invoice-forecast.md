---
description: Lance InvoicePredictor — forecast cash flow 30/60/90j depuis Stripe, écrit data/finance/forecast_<date>.md (P22.F Sprint 10)
---

# /run-invoice-forecast

Slash command Claude Code invoquée manuellement ou par Task Scheduler
(`argos-ops-invoice-forecast`, hebdomadaire) **sur l'ordi du fondateur** (D-017).

## Procédure

1. Lance `uv run python scripts/run_invoice_predictor.py` (foreground, ~5-15 s selon volume Stripe).
2. Lis la sortie loguru et l'exit code.
3. **Si exit 0** : le forecast a été écrit dans `data/finance/forecast_<YYYY-MM-DD>.md`. Affiche au founder :
   - le `output_summary` (`30d=X 60d=Y 90d=Z subs=N excluded=M`)
   - le chemin du fichier généré
   - si une fenêtre est très basse (< 1 000 €), suggère de vérifier la cohérence avec `BurnRateMonitor`
4. **Si exit 1** : cause probable `STRIPE_SECRET_KEY` manquant ou Stripe API down. Propose la correction.

## Notes

- Hypothèses fortes : pas de churn projeté, renouvellement à `current_period_end`. Pas un modèle ML, juste une jauge "si tout reste stable".
- Sub `past_due` / `canceled` / `unpaid` sont exclues (`n_subs_excluded`).
- Idempotent à la date — ré-exécuter le même jour écrase le fichier précédent.
- Pas de notif Discord automatique. Le forecast est consommé par `BurnRateMonitor` ou par le founder direct.

## Voir aussi

- Code : [argos_ops/agents/invoice_predictor.py](../../argos_ops/agents/invoice_predictor.py)
- Helper : [argos_ops/finance/cash_flow.py](../../argos_ops/finance/cash_flow.py)