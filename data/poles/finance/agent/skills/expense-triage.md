---
id: expense-triage
role: treasury
references: run-expense-audit
guardrails: [3-regles-deterministes, journal-append-only, lecture-seule-cockpit]
---

Audite le dernier export CSV Qonto (`expenses.audit`) selon 3 règles déterministes
: montant outlier (> 3× la médiane), doublon (même vendor/montant/date — double
prélèvement), nouveau vendor (vs journal `vendors.md`). Outliers et doublons sont
remontés en priorité (fraude / erreur). Le journal vendors est append-only (mis à
jour par le script, jamais par le cockpit en lecture). Aucune API Qonto (D-017).
