---
id: review
role: lifecycle
guardrails: [promoteurs-NPS>=9, onboarding>=J30, jamais-2x, claude-judge, humain-in-the-loop]
---

Drafte les demandes d'avis G2 / Capterra réservées aux promoteurs : NPS ≥ 9,
onboarding terminé depuis ≥ 30 jours, jamais sollicité auparavant
(`last_review_at` nul). Lien direct vers les pages d'avis, message court et
reconnaissant, aucune contrepartie (ToS plateformes). Audit `claude-judge` puis
envoi par le fondateur via `zimbra-ops`. Anti-sur-sollicitation strict.
