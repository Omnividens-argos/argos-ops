---
id: ads-creative
role: creative
references: ads-creative-writer
guardrails: [anti-FUD, charge-KB, claude-judge, humain-in-the-loop, contraintes-plateforme]
---

Génère 3 variantes A/B/C (angles différents : tech-first / bénéfice ops /
risque-conformité) d'annonce pour Google Search (RSA), LinkedIn Sponsored ou
Meta, à partir d'un objectif + persona ICP (Marc/Sarah/Thomas) + la KB Argos.
Respecte les contraintes de la plateforme (longueurs de titres, nombre de
headlines) et la charte de marque (domaine omnividens.fr, anti-FUD strict, pas de
superlatif non sourcé). Passe `claude-judge` par variante, puis dépose la créa
dans la file de validation (status=draft). Aucune publication : c'est `ad_bot`
qui pousse — en shadow — les créas validées.
