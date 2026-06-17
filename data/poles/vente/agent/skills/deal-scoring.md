---
id: deal-scoring
role: scoring
references: run-deal-scoring
guardrails: [heuristique-auditable, humain-prioritaire, jamais-de-promesse, read-only-pipe]
---

Score le risque de chaque deal du pipe (`deals/pipe.yaml`) et flag les `stalled`
(inactivité > seuil par stade : discovery 14j, demo_scheduled 7j, proposal_sent
14j, contract_sent 30j). Score 0-100 = inactivité + montant + stade. Heuristique
100 % auditable (RGPD § 22), pipe en lecture seule. Propose un angle de relance
contextualisé par les notes, sans jamais promettre remise/feature/date.
