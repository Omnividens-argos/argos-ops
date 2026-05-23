---
description: Lance DarkWebMonitor (MVP) — domaines clients dans les breaches publiques HIBP. Silence si aucun hit.
---

# /run-dw-monitor

Slash command Claude Code invoquée manuellement ou par cron mensuel
**sur l'ordi du fondateur** (D-017).

## Procédure

1. Lance `uv run python scripts/run_dw_monitor.py` (foreground,
   ~5-20 sec).
2. Lis la sortie loguru et l'exit code.
3. **Si exit 0 et `output_summary` commence par `silence (vert)`** :
   aucun nouveau domaine prospect/client n'apparaît dans la base HIBP.
4. **Si exit 0 et `output_summary` commence par `alert pushed`** : un
   embed jaune liste les hits domaine ↔ breach. Sell point typique :
   « Nous avons relevé ~X comptes de votre domaine dans le breach Y de
   2023. Argos peut auditer votre exposition continue. »
5. **Si exit 0 et `output_summary` commence par `silence (aucun
   domaine déclaré)`** : ajouter au moins des prospects dans
   `data/crm/customers.yaml`.

## Notes (MVP — limitations)

- Endpoint utilisé : `/api/v3/breaches` (liste statique, pas d'auth) +
  croisement local par domaine. Pas de domain search authentifié (qui
  exige vérification de propriété du domaine).
- Pour Argos prospecter sur un domaine que le founder ne possède pas,
  c'est ce MVP qui sert : on lit *quels* breaches publics ont impacté
  ce domaine, pas la liste détaillée des comptes.
- Garde-fou éthique : aucun email individuel n'est affiché — on
  reporte seulement le total agrégé `PwnCount` publié par HIBP.
- L'état "déjà vu" : `data/darkweb/seen_hits.json`.
