---
description: Lance IntentSignalsBot — capte signaux d'achat publics (breaches, embauches CISO, levées) → data/sales/signals/<date>.yaml + alerte Discord top-5.
---

# /run-intent-signals

Slash command Claude Code invoquée manuellement ou par Task Scheduler (`argos-ops-intent-signals`, cadence 2x/jour, 8h et 16h Paris) **sur l'ordi du fondateur** (D-017).

## Procédure

1. Lance `uv run python scripts/run_intent_signals.py` (foreground, ~5-20 sec selon nombre de flux).
2. Lis la sortie loguru et l'exit code.
3. **Si exit 0 et `silence (no sources)`** : `data/sales/signals/sources.yaml` absent. Le founder doit déclarer au moins une catégorie (breach, ciso_hire, fundraise, cve_critical).
4. **Si exit 0 et `captured=0`** : flux atteints, zéro signal (peut être un weekend ou un jour calme). Pas d'action.
5. **Si exit 0 et `captured > 0`** :
   - Si `top_relevance >= 70` : Discord embed orange poussé sur ops_logs. Propose au founder de croiser avec l'inbox ProspectMiner et de prioriser les leads concernés.
   - Sinon : Discord embed jaune (signaux capturés mais aucun très chaud). Propose un check rapide.
6. **Si exit 1** : YAML sources mal formé ou crash réseau hard.

## Notes

- Format `data/sales/signals/sources.yaml` (toutes les clés optionnelles) :
  ```yaml
  breach:
    - "https://www.cert.ssi.gouv.fr/feed/"
  ciso_hire:
    - "https://www.linkedin.com/jobs/search/.../public.rss"
  fundraise:
    - "https://news.crunchbase.com/feed/"
    - "https://www.maddyness.com/feed/"
  cve_critical:
    - "https://nvd.nist.gov/feeds/xml/cve/misc/nvd-rss.xml"
  ```
- Mots-clés ICP boostés dans le scoring : `saas`, `scale-up`, `pme`, `rgpd`, `nis2`, `ransomware`, `breach`, `fuite`.
- Output quotidien : `data/sales/signals/<YYYY-MM-DD>.yaml` (réécrit si re-lancé même jour).
- Breaker associé : `IntentSignalsBot` (P15).
