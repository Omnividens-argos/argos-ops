---
description: Lance UptimeMonitor — ping les endpoints publics, alerte Discord si down/4xx (silence si tout up)
---

# /run-uptime

Slash command Claude Code invoquée manuellement ou par Task Scheduler
(`argos-ops-uptime`, toutes les 5 min) **sur l'ordi du fondateur** (D-017).

## Procédure

1. Lance `uv run python scripts/run_uptime_monitor.py` (foreground, ~1-3 sec selon le nombre d'endpoints).
2. Lis la sortie loguru et l'exit code.
3. **Si exit 0 et `output_summary` commence par `silence (vert)`** : tous les endpoints répondent en 2xx/3xx.
4. **Si exit 0 et `output_summary` commence par `silence (aucun endpoint)`** : `data/uptime/endpoints.yaml` vide ou absent. Propose au founder d'ajouter au moins l'URL du site public.
5. **Si exit 0 et `output_summary` commence par `alert pushed`** : un embed jaune (4xx) ou rouge (5xx/timeout/refused) a été poussé. Lis le summary (ex : `2 up · 0 degraded · 1 down`). Propose au founder :
   - Si OVH down : check status.ovh.com
   - Si admin panel 4xx : check les logs `docker logs sechunter-ops-1` côté serveur
   - Si tout down : check la connexion réseau du host
6. **Si exit 1** : erreur dans la lecture du YAML (mal formé).

## Notes

- Format `data/uptime/endpoints.yaml` :
  ```yaml
  endpoints:
    - name: "Site public"
      url: "https://omnividens.fr/"
    - name: "Admin Panel"
      url: "https://ops.omnividens.fr/"
      timeout_seconds: 15  # optionnel, défaut 10
  ```
- Le check fait un GET (avec follow_redirects=True). Pour les endpoints qui n'autorisent que HEAD, override avec `method: HEAD` dans le YAML.
- Mutualisé avec `SSLExpirer` qui lit le même fichier — quand on ajoute un endpoint, les 2 watchers le picorent.
