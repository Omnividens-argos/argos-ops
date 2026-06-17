---
id: contract-doc
role: billing
references: draft-proposal
guardrails: [idempotent, gate-conformite, pdf-best-effort, humain-signe]
---

Génère devis et contrats (CGV/MSA) à partir d'un contexte
`docs/contexts/<deal>.yaml` via `docs.generate_proposal` / `generate_contract`
(réutilise `argos_ops.sales.templates`). PDF tenté via pandoc, sinon Markdown seul
(D-009). **Gate conformité** : la génération est refusée tant que la conformité
RGPD/AI Act est bloquante (onboarding d'un nouveau traitement). Le fondateur relit
et signe — aucun envoi automatique.
