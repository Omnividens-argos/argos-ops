---
description: Lance BreachWatcher — croise breaches publics (CERT-FR + HIBP) avec data/crm/customers.yaml. Silence Discord si aucun match.
---

# /run-breach-watch

Slash command Claude Code invoquée manuellement ou par cron hebdomadaire
**sur l'ordi du fondateur** (D-017).

## Procédure

1. Lance `uv run python scripts/run_breach_watcher.py` (foreground,
   ~5-15 sec selon le réseau).
2. Lis la sortie loguru et l'exit code.
3. **Si exit 0 et `output_summary` commence par `silence (vert)`** :
   aucun domaine prospect/client n'apparaît dans la fenêtre 30 jours.
4. **Si exit 0 et `output_summary` commence par `silence (aucun client)`** :
   `data/crm/customers.yaml` vide ou absent. Le founder doit y déclarer
   au moins ses clients existants pour activer le watcher.
5. **Si exit 0 et `output_summary` commence par `alert pushed`** : un
   embed (jaune ou rouge) liste les croisements. Pour chaque match :
   - **Rouge** (keywords critiques : passwords / credentials / api_keys /
     ssh) : drafter immédiatement un mail proactif au client touché,
     avec recos d'actions (rotation MDP, rotation tokens).
   - **Jaune** : surveiller mais pas d'action urgente.

## Notes

- Sources : flux RSS `cert.ssi.gouv.fr/alerte/feed/` + API HIBP `/breaches`
  (publique, pas de clé requise pour la liste).
- Fenêtre par défaut : 30 jours (override via le constructeur).
- Garde-fou éthique : **aucun dump réel n'est téléchargé**, seules les
  métadonnées publiques. Le résultat reste local
  (`data/breaches/last_run.json`) — ne JAMAIS partager le détail "ce
  client est victime" en dehors du founder.
