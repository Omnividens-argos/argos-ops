---
id: weekly-synthesis
role: strategy
references: argos_ops/poles/direction/synthesis.py
guardrails:
  - Ne jamais déclasser un signal critique remonté par un pôle (le cerveau ne minimise pas).
  - Fallback heuristique obligatoire si le cerveau est OFF.
---

Compose la **synthèse de la semaine** : état global de la flotte, points
saillants, risques. Sous D-017 le cerveau (`claude -p`) rédige le récit ; le
fallback déterministe reste `build_synthesis`. C'est le cœur narratif du cockpit.
