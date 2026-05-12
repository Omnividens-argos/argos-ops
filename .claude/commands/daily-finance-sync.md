---
description: Sync Stripe quotidienne (subs + factures + dunning + alerte MRR)
---

# /daily-finance-sync

Slash command Claude Code invoquée tous les matins par cron / Task Scheduler
(`0 6 * * *` Paris) **sur l'ordi du fondateur** (D-017). Pull Stripe,
synchronise les `companies`, calcule le MRR/ARR, envoie les relances
impayées (J+3 / J+7 / J+15), et notifie Discord en cas de baisse > 5 %.

## Procédure

1. Lance le script `uv run python scripts/run_finance_bot.py`
   (foreground, ~5-30 s selon le volume Stripe).
2. Lis la sortie loguru et l'exit code.
3. **Si exit 0 (status=success)** :
   - Lis le `output_summary` (`mrr=X arr=Y dunning_sent_3=N ...`)
   - Si `mrr_delta` est négatif > 5 %, alerte le fondateur : breaker
     potentiel + propose d'examiner les churns récents
   - Si `dunning_sent_15 > 0` (relances escalades envoyées), avertis
     que des suspensions sont à prévoir sous 48 h
4. **Si exit 1 (status=failed)** :
   - Causes communes : `STRIPE_SECRET_KEY` manquant ou expiré,
     `EMAIL_USER/PASSWORD` manquants, container `argos-postgres-local`
     arrêté, Stripe API rate limit (très rare)
   - Propose la correction au fondateur, ne tente pas de fix automatique
5. **Si exit 1 (status=killed_by_breaker)** :
   - Le breaker `FinanceBot` est tripé. Note le motif et propose un reset

## Notes

- L'agent **n'envoie pas de notif systématique** sur Discord — uniquement
  un embed dans le canal `alerts` (fallback `ops_logs`). Le digest matinal
  reprendra les KPIs MRR via `agent_runs.output_summary` (P19+)
- Les relances dunning sont **idempotentes** : pas de double envoi grâce
  au check `interactions.judge_verdict='dunning_X'` + subject contient
  l'invoice_id
- Convention couleur de l'embed Discord :
  - Vert : MRR stable ou en hausse, 0 impayé
  - Jaune : impayés en cours OU dunning J+15 envoyé
  - Rouge : MRR baisse > 5 % vs S-1

## Voir aussi

- Code agent : [`argos_ops/agents/finance_bot.py`](../../argos_ops/agents/finance_bot.py)
- Wrapper Stripe : [`argos_ops/integrations/stripe_client.py`](../../argos_ops/integrations/stripe_client.py)
- Skill : [`.claude/skills/stripe-ops/`](../skills/stripe-ops/)
- Décisions : [D-017](../../docs/DECISIONS.md) (local-first)
