---
id: ai-act-classifier
role: compliance
references: run-ai-act-audit
guardrails: [enum-canonique, garde-fou-bloquant, transparence-art-13, humain-prioritaire]
---

Valide la classification AI Act de chaque système IA déclaré
(`compliance.load_ai_act_registry`) selon l'enum canonique minimal / limited / high
/ prohibited (`classify_ai_act_risk`). Un système `unclassified` est un gap de
transparence (art. 13). **Garde-fou bloquant** : un système `prohibited` (art. 5)
— ou un registre absent — gèle l'onboarding. Ne déclasse jamais un risque ; en cas
de doute, conserve la classe la plus sévère.
