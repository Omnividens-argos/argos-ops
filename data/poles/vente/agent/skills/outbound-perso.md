---
id: outbound-perso
role: outreach
references: outbound-personalizer
guardrails: [source-publique-citee, fait-date-<60j, zero-flatterie, claude-judge, opt-out-HMAC, humain-in-the-loop]
---

Génère **1 ligne hyper-personnalisée** (80-180 chars) en tête d'une touche de
séquence cold email Argos, à partir d'une fiche `enriched/<slug>.md`. Règle n°1
anti-fake-perso : citer une source publique précise et un fait spécifique daté de
moins de 60 jours — jamais de « j'ai vu votre profil » ni de flatterie générique.
Audit `claude-judge` avant insertion. Disqualifie le lead si email perso (RGPD),
si BANT < 40, ou si la conformité Bloctel a gelé l'outbound (Python tranche).
