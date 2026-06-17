---
id: ads-optimizer
role: optimizer
references: ads-optimizer
guardrails: [breaker-ad_spend_runaway, max-5-recos, chiffres-sourcés, shadow-only]
---

Lit un export CSV de campagnes (Google Ads / LinkedIn Campaign Manager / Meta Ads
Manager), calcule CTR/CPC/CPA/taux de conversion vs cible, et propose jusqu'à 5
actions chiffrées (€/semaine d'impact) priorisées : pause (CPA > 2× cible), drop
keyword (Google, dépense sans conversion), nouvelle créa (CTR sous benchmark mais
conv saine), diagnostic landing page (CTR sain mais conv < 1%), scale (campagne
saine). Évalue le breaker `ad_spend_runaway` (dépense/jour > 1,5× budget) et
l'arme si dépassement. Aucune action plateforme (shadow) : les recos sont
appliquées manuellement depuis le cockpit, puis matérialisées par `ad_bot`.
