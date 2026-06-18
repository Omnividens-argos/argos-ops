---
id: okr-review
role: strategy
references: argos_ops/poles/direction/okr.py
guardrails:
  - Comparer toujours au prorata temporis (pas à 100 % en milieu de trimestre).
  - Les valeurs `actual` sont une donnée founder — le skill ne les invente jamais.
---

Revoit les **OKR** du trimestre : compare la progression de chaque key result au
prorata temporis et signale les `at_risk` / `off_track`. Propose des leviers de
redressement, sans modifier les cibles.
