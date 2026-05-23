---
description: Lance ReviewBot — drafte les demandes d'avis G2/Capterra pour les promoteurs (NPS ≥ 9, onboarding ≥ J+30). Humain envoie via zimbra-ops après audit claude-judge.
---

# /run-review-campaign

Slash command Claude Code invoquée manuellement (mensuel recommandé) ou par Task Scheduler (`argos-ops-reviews`, hebdo).

## Procédure

1. Lance `uv run python scripts/run_review_bot.py`.
2. **Si `silence (no customers)`** : pas de CRM CS.
3. **Si `drafted > 0`** : embed Discord jaune. Pour chaque `data/reviews/drafts/<id>.md` :
   - Audite via `claude-judge` (tone — pas de pressing).
   - Peaufine si besoin.
   - Envoie via `zimbra-ops`.
   - Patche manuellement `last_review_at: <today>` dans `data/cs/customers.yaml`.

## Notes

- Filtres stricts (anti-pollution promo) :
  - `onboarding_done_at` ≥ J-30
  - `last_review_at` est null (jamais sollicité)
  - `last_nps ≥ 9` (promoteur uniquement)
- Cibles G2 + Capterra. Le mail mentionne les 2 URLs, le client choisit.
- "Pas de relance" mentionné explicitement (engagement écrit).
- Idempotent : un draft existant n'est pas recréé.
- Skills : `claude-judge` (P14), `zimbra-ops` (D-018).
- Breaker : `ReviewBot` (P15).
