---
id: board-pack
role: reporting
references: argos_ops/poles/direction/board.py
guardrails:
  - KPIs finance = snapshot fichier (jamais d'appel Stripe en lecture cockpit).
  - NRR reste un placeholder tant que les cohortes ne sont pas fiables.
---

Assemble le **board pack** mensuel pandoc-ready : MRR / ARR / burn / runway / NRR
(snapshot finance) + section opérations dérivée de la vue d'ensemble flotte.
Document interne investisseurs, exportable en PDF.
