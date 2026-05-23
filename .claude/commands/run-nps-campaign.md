---
description: Lance NPSCollector — drafte les demandes NPS post-onboarding J+14 et post-renew J+21 depuis data/cs/customers.yaml. Humain envoie via zimbra-ops.
---

# /run-nps-campaign

Slash command Claude Code invoquée manuellement ou par Task Scheduler (`argos-ops-nps`, hebdo lundi 10h Paris).

## Procédure

1. Lance `uv run python scripts/run_nps_collector.py`.
2. **Si exit 0 et `silence (no customers)`** : `data/cs/customers.yaml` absent.
3. **Si exit 0 et `drafted=0`** : aucun NPS dû → silence Discord.
4. **Si exit 0 et `drafted > 0`** : embed Discord jaune. Pour chaque draft `data/nps/drafts/<id>-<reason>.md` :
   - Invoque `claude-judge` pour audit factual + tone (anti-pressuring).
   - Si OK : envoie via `zimbra-ops`.
   - Patche manuellement `last_nps_at: <today>` dans `data/cs/customers.yaml` après envoi (et `last_nps: <score>` quand la réponse arrive).

## Notes

- Deux déclencheurs :
  - **post-onboarding** : `onboarding_done_at ≥ J-14` et aucun NPS depuis
  - **post-renew** : `last_renew_at ≥ J-21` et aucun NPS depuis ce renew
- Ton délibérément non-poussif : « pas de relance automatique » mentionné dans le mail.
- Idempotent : draft existant non recréé. Si le founder veut regénérer, suppression manuelle.
- Audit `claude-judge` recommandé pour vérifier qu'on n'introduit pas de biais de formulation (anchor sur 9-10).
- Skill réutilisé : `zimbra-ops` (D-018), `claude-judge` (P14).
- Breaker associé : `NPSCollector` (P15).
