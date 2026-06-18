"""Pôle 2 — **Marketing / Comm** (archi v2, S2).

Acquisition organique : le pôle lit la **Veille** (cross-pôle) pour nourrir son
angle éditorial, son agent (``MarketingAgent``) synthétise des recommandations
de contenu routées par canal, et ses scripts déterministes
(``content_bot`` / ``social_analytics`` / ``media_list_builder``) écrivent leur
mémoire (publications, engagement, médias). 100 % fichiers, local-first (D-017).
"""

from __future__ import annotations
