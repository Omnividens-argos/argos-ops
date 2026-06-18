"""Pôle 3 — **Pub** (acquisition payante, archi v2, S3).

Acquisition *payante* : créas, optimisation des campagnes et **garde-fous
budget**. Le pôle est branché en aval de la Veille (tendances / pricing) et du
Marketing (ton / mots-clés), et en aval de la Finance (budget — lecture
défensive tant que le pôle Finance n'a pas de mémoire). Son agent (``PubAgent``)
lit cette mémoire cross-pôle + sa propre mémoire et **synthétise un plan
d'actions** (idées de créa + actions budget), borné par le **circuit breaker
``ad_spend_runaway``** (« le LLM propose, Python tranche »).

Ses scripts déterministes :

- ``ads_optimizer`` : lit un export CSV de campagnes, calcule CTR/CPC/CPA et
  produit des recommandations chiffrées (€/semaine) ; met à jour la jauge de
  budget et arme le breaker en cas d'emballement.
- ``ad_bot`` : pousseur **shadow** (D-026) — enregistre ce qu'il *publierait*
  (créas validées + recos appliquées), borné par le breaker. Aucun appel
  plateforme tant que le mode live n'est pas activé.

100 % fichiers, local-first (D-017) : aucune API tierce, aucun secret ici.
"""

from __future__ import annotations
