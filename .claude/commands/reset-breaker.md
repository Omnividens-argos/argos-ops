---
description: Reset un circuit breaker Argos Ops (P15). Sans argument, liste les breakers tripped.
---

# /reset-breaker

Reset manuel d'un circuit breaker Argos Ops après correction de la cause racine
(cf. P15.2 du plan, [`docs/ARGOS_OPS_PLAN.md`](../../docs/ARGOS_OPS_PLAN.md)).

## Usage

- `/reset-breaker` (sans argument) — liste les breakers actuellement tripped
- `/reset-breaker <name>` — reset le breaker nommé

## Workflow

1. **Avant de reset** : confirme que la cause racine du trip est corrigée.
   - `mrr_drop_critical` → la baisse MRR est-elle expliquée (churn ponctuel,
     mauvaise classification Stripe, bug FinanceBot) ?
   - `stripe_api_error_burst` → la clé Stripe restreinte est-elle toujours
     valide (test : `uv run python -c "import stripe; ..."`) ?
   - `email_smtp_failures_burst` → le mot de passe Zimbra OVH n'a-t-il pas
     été changé sans propagation à `.env.local` ?

2. **Exécuter le reset** :

   ```bash
   uv run python scripts/reset_breaker.py <name>
   ```

3. **Vérification** : relancer manuellement l'agent concerné pour valider que
   le run passe sans re-trip :

   ```bash
   uv run python scripts/run_finance_bot.py    # si FinanceBot
   uv run python scripts/run_email_bot.py      # si EmailBot
   ```

## Breakers existants (Sprint 1)

| Nom | Agent | Trigger automatique | Reset après |
|-----|-------|---------------------|-------------|
| `mrr_drop_critical` | FinanceBot | MRR -10 % ou plus sur 7 j | Investigation churn + audit Stripe |
| `stripe_api_error_burst` | FinanceBot | ≥ 3 runs `failed` sur 24 h | Audit clé restreinte + test API |
| `email_smtp_failures_burst` | EmailBot | ≥ 3 runs `failed` sur 24 h | Vérif IMAP login + password Zimbra |
| `DigestBuilder` / `EmailBot` / `FinanceBot` | global kill switch | jamais auto (manuel uniquement) | quand le fondateur décide |

**Pas de reset automatique** : la décision de réenclencher un agent appartient
toujours à l'humain (D-019 — Argos Ops sans pilote automatique critique).

## Future (P12+)

- `ad_spend_runaway` (P12 AdBot) — dépense > 1.5× budget
- `email_spam_complaints` (P13 OutboundBot) — > 3 complaints/jour
- `outbound_bounce_rate` (P13 OutboundBot) — > 5 % bounce
- `judge_disagreement` (P14 ClaudeJudge) — > 20 % de queued/jour

Cf. § 15.1 de [`ARGOS_OPS_PLAN.md`](../../docs/ARGOS_OPS_PLAN.md) pour la liste exhaustive.
