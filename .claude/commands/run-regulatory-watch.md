---
description: Lance RegulatoryWatcher — flux RSS UE/CNIL/ANSSI filtrés par keywords RGPD/AI Act/NIS2/DORA. Silence si rien de nouveau.
---

# /run-regulatory-watch

Slash command Claude Code invoquée manuellement ou par cron hebdomadaire
**sur l'ordi du fondateur** (D-017).

## Procédure

1. Lance `uv run python scripts/run_regulatory_watcher.py` (foreground,
   ~5-30 sec selon le nombre de sources et la latence des flux RSS).
2. Lis la sortie loguru et l'exit code.
3. **Si exit 0 et `output_summary` commence par `silence (vert)`** :
   rien de nouveau qui matche les keywords pertinents sur les flux
   officiels.
4. **Si exit 0 et `output_summary` commence par `silence (aucune
   source)`** : `data/regulatory/sources.yaml` vide ou absent.
   Proposer au founder d'ajouter au moins CNIL + ANSSI + Commission UE.
5. **Si exit 0 et `output_summary` commence par `alert pushed`** : un
   embed jaune liste les nouvelles entrées. Le founder doit :
   - Cliquer sur les liens pour lire l'entrée complète
   - Décider si une décision compliance / produit s'impose (note dans
     `docs/DECISIONS.md` si oui)
   - Le watcher persiste les GUIDs vus → on n'alertera plus sur ces
     entrées au prochain run.

## Notes

- Sources et keywords customizables via `data/regulatory/sources.yaml` ::

  ```yaml
  sources:
    - name: CNIL
      rss_url: https://www.cnil.fr/feed.xml
    - name: Commission UE Justice
      rss_url: https://commission.europa.eu/info/.../rss
  keywords:
    - rgpd
    - ai act
    - nis2
    # custom-keyword
  ```
- Cache 24 h via `_fetcher_base` : un re-run dans la journée tape juste
  le cache disque, pas les serveurs CNIL/ANSSI.
