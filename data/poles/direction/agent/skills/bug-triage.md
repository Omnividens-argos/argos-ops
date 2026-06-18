---
id: bug-triage
role: product
references: argos_ops/poles/direction/bugs.py
guardrails:
  - Le cerveau ne déclasse jamais un signal mots-clés plus sévère.
  - Un bug P0 ouvert gèle la publication d'artefacts publics.
---

Trie les **bugs** par sévérité (P0 / P1 / P2) et propose un label. Les P0 sont
des faits `important` qui arment le garde-fou release. Mode shadow : aucun label
posé automatiquement (le fondateur applique via `gh issue edit`).
