---
id: cashflow-forecast
role: treasury
references: run-invoice-forecast
guardrails: [hypothese-explicite, pas-de-churn-projete, lecture-seule]
---

Synthétise le forecast cash flow 30/60/90j (`billing.forecast`) et le combine au
burn/runway (`treasury.burn_report`) pour donner une jauge « combien je rentre si
tout reste stable vs combien je brûle ». Hypothèse explicite : tout le portefeuille
renouvelle à la prochaine échéance, aucun churn projeté (pas de modèle ML — D-017).
Lecture seule ; le résultat alimente l'alerte runway, jamais une décision de
dépense automatique.
