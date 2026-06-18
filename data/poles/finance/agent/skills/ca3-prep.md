---
id: ca3-prep
role: fiscal
references: run-tax-prep
guardrails: [draft-uniquement, aucun-depot-dgfip, humain-audite, doc-important-protege]
---

Prépare un brouillon de déclaration TVA CA3 mensuelle (base HT = MRR proxy) + une
estimation IS prévisionnel PME (15 % puis 25 %), via `taxes.current_ca3` /
`docs.generate_ca3`. Draft uniquement : aucun dépôt sur impots.gouv.fr — le
fondateur (ou son comptable) audite avant le 19 du mois M+1. Le fait fiscal est
écrit avec le flag `important` (protégé du nettoyage mémoire). TVA déductible à
renseigner à la main depuis les achats Qonto.
