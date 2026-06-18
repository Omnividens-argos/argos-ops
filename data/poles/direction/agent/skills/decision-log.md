---
id: decision-log
role: governance
references: argos_ops/poles/direction/decisions.py
guardrails:
  - Idempotent par titre (jamais deux fois la même décision).
  - Écrit le journal LOCAL du pôle, jamais le docs/DECISIONS.md canonique du repo.
---

Tient le **journal des décisions** structurantes (ID `D-NNN`, date, partie,
décision, pourquoi). Append-only : une décision actée ne se réécrit pas. Connaissance
de gouvernance protégée du nettoyage (faits `important`).
