---
id: seo-brief
role: writer
channel: blog
references: seo-brief-writer
guardrails: [charge-KB, claude-judge, humain-in-the-loop]
---

Génère un brief blog SEO structuré (titre, outline H2/H3, sources, meta, internal
links) à partir d'un mot-clé (souvent issu d'un signal `seo_movement` de la
Veille) + la KB du pôle. Pas de SERP scraping (option A). Anti-générique IA via
charge KB systématique. Sortie = brief en file de validation (canal blog).
