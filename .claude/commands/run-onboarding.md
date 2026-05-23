---
description: Lance OnboardingBot — drafte les emails J+0/J+7/J+30 dus depuis data/cs/customers.yaml. Idempotent. Humain envoie via zimbra-ops.
---

# /run-onboarding

Slash command Claude Code invoquée manuellement ou par Task Scheduler (`argos-ops-onboarding`, quotidien 8h30 Paris après le digest) sur l'ordi du fondateur (D-017).

## Procédure

1. Lance `uv run python scripts/run_onboarding_bot.py`.
2. **Si exit 0 et `silence (no customers)`** : `data/cs/customers.yaml` absent. Le founder doit créer son CRM CS à la main.
3. **Si exit 0 et `drafted=0`** : aucune étape J+0/J+7/J+30 due → silence Discord.
4. **Si exit 0 et `drafted > 0`** : Discord embed jaune posté. Founder lit `data/onboarding/drafts/<customer>-J<step>.md`, peaufine si besoin, envoie via `zimbra-ops`.

## Notes

- Format `data/cs/customers.yaml` :
  ```yaml
  customers:
    - customer_id: "acme-sa"
      name: "Acme SA"
      contact_email: "marc@acme.fr"
      contact_name: "Marc Dupont"
      plan: "pro"
      signup_date: "2026-05-15"
      onboarding_done_at: null
      usage: { scans_this_month: 0, scans_quota: 200, last_login_days_ago: null }
      tickets_30d: 0
  ```
- Étapes : J+0 bienvenue, J+7 check premier scan, J+30 bilan + propose call.
- Idempotent : un draft existant n'est pas recréé. Si le founder veut regénérer, il supprime le fichier d'abord.
- Breaker associé : `OnboardingBot` (P15). Reset via `/reset-breaker OnboardingBot`.
- **Pas d'envoi automatique** — humain valide chaque mail.
