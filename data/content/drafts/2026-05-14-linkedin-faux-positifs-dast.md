---
channel: linkedin
status: draft
date_created: 2026-05-14
posted_at: null
topic: "Faux positifs DAST — l'oracle comme preuve reproductible"
angle: "Pourquoi un finding Argos n'est jamais « à vérifier » — notre obsession FP racontée via les 5 oracles."
character_count: 1394
word_count: 238
kb_sources:
  - "argos_features.md§Oracle (web.sql_injection, web.rce_command, OOB / time-based / baseline-diff)"
  - "tone_of_voice.md§3 (vocabulaire à privilégier — oracle, preuve reproductible, FP)"
  - "tone_of_voice.md§4 (vocabulaire banni — pas de « ravi de », pas de FUD)"
  - "ICP.md§3 (Marc — anti-FP, recherche preuve technique)"
  - "competitor_compare.md§12 (anti-disparagement — pas de comparaison nominative)"
cta: "https://omnividens.fr"
url_posted: null
---

On a banni un mot du produit : « à vérifier ».

Un finding Argos n'est jamais une suspicion. Soit c'est une preuve, soit on le supprime du rapport.

Notre principe : pas de finding sans oracle. Cinq oracles possibles — out-of-band (OOB), time-based, baseline diff, error-based ancré, status-code whitelist. Tant qu'on ne déclenche pas l'un d'eux, on ne lève pas le drapeau.

Exemple concret. Une SQLi blind sur `acme.fr/products?id=`. Pas de réponse différente, pas d'erreur visible. On déclenche une time-based : `SLEEP(5)` injecté, la réponse arrive à 5 034 ms. Reproductible, ancré sur une fonction SQL native. Finding levé. Le dev a la requête exacte, le delta de latence, le payload.

Pas de « possible XSS dans ce champ ». Pas de « probablement vulnérable ». Pas de tableur de 800 alertes dont 600 sont du bruit.

Concrètement pour un dev : tu lis le ticket, tu rejoues la requête dans Burp ou cURL en 30 secondes, tu vois la latence ou le callback OOB tomber, tu corriges. Pas de session de tri à 23 h avant l'audit.

Le coût des faux positifs n'est pas dans le scanner — il est dans l'heure que ton équipe passe à les trier. Argos déplace ce coût en amont, dans le moteur.

Le DAST a mauvaise réputation parce qu'on a longtemps confondu suspicion et preuve. C'est réparable.

Plus de détails sur l'approche oracle → https://omnividens.fr

#DAST #AppSec #DevSecOps #Pentest #FauxPositifs
