---
id: reconcile-helper
role: treasury
references: run-reconcile
guardrails: [match-heuristique, lecture-seule, orphelins-en-priorite]
---

Rapproche les payouts Stripe déclarés avec les crédits « STRIPE » du dernier export
Qonto (`reconcile.reconcile_report`) : match par montant (à 1 centime) et date (J à
J+5). Met en avant les **orphelins** (payout sans crédit, ou crédit sans payout) —
priorité d'investigation (bug d'export ou fraude). Lecture seule, aucune écriture
bancaire ; le fondateur tranche sur les orphelins.
