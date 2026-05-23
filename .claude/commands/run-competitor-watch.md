---
description: Lance CompetitorWatcher — scrape hebdo pages /pricing et /features des concurrents et alerte sur diff (silence si stable)
---

# /run-competitor-watch

Slash command Claude Code invoquée manuellement ou par Task Scheduler
(``argos-ops-competitor-watch``, hebdomadaire) **sur l'ordi du
fondateur** (D-017).

## Procédure

1. Lance ``uv run python scripts/run_competitor_watcher.py`` (foreground,
   ~5-30 sec selon nombre de cibles, cache 24h sauf ``--force``).
2. Lis la sortie loguru et l'exit code.
3. **Si exit 0 et ``output_summary`` commence par ``silence (vert)``** :
   aucune page concurrent n'a bougé depuis le snapshot précédent.
4. **Si exit 0 et ``output_summary`` commence par ``silence (aucune
   cible)``** : ``data/competitors/targets.yaml`` est vide ou absent.
   Proposer au founder d'ajouter au moins 3 concurrents (Acunetix,
   Detectify, Intruder).
5. **Si exit 0 et ``output_summary`` commence par ``alert pushed``** :
   un embed jaune liste les pages qui ont bougé. Pour chaque diff, le
   founder doit :
   - Ouvrir l'URL pour identifier visuellement le changement (pricing
     baissé ? feature ajoutée ? case study ?).
   - Décider si ça impacte le positionnement Argos (à reporter dans le
     fichier de veille).

## Notes

- Format ``data/competitors/targets.yaml`` :
  ```yaml
  targets:
    - name: "Acunetix"
      section: "pricing"
      url: "https://www.acunetix.com/vulnerability-scanner/pricing/"
    - name: "Detectify"
      section: "features"
      url: "https://detectify.com/features/"
  ```
- Cache disque 24 h via ``argos_ops.agents._fetcher_base`` : un re-run
  manuel dans la journée renvoie depuis le cache sans frapper le site
  cible.
- User-Agent explicite ``Argos-Ops/competitor-watcher`` — on ne se
  cache pas, le site peut bloquer s'il veut.
- Premier run = baseline silencieuse (aucune diff possible). Les
  changements suivants déclenchent une alerte unique : on persiste le
  nouveau hash pour ne pas réalerter au tour suivant.