---
id: brand-check
role: brand
references: claude-judge
guardrails: [deterministe-python, anti-FUD, domaine-canonique]
---

Contrôle de marque déterministe d'un draft avant validation : applique
`charter.brand_check` (termes bannis anti-FUD, domaine canonique omnividens.fr)
puis l'audit `claude-judge` (factual / tone / legal). « Le LLM propose, Python
tranche » : un écart mécanique bloque la validation tant qu'il n'est pas corrigé.
