---
description: Lance ReconcileBot — rapproche payouts Stripe (data/finance/stripe_payouts.yaml) avec crédits Qonto (dernier CSV). Silence Discord si tout matche.
---

# /run-reconcile

Slash command Claude Code invoquée manuellement après chaque export Stripe
payouts + Qonto CSV **sur l'ordi du fondateur** (D-017).

## Pré-requis

- `data/finance/stripe_payouts.yaml` — export payouts depuis Stripe Dashboard
- `data/expenses/<YYYY-MM>.csv` — dernier export Qonto (déjà utilisé par ExpenseAuditor)

## Procédure

1. Lance `uv run python scripts/run_reconcile_bot.py` (foreground, < 1 s).
2. **Si `silence (vert)`** : tous les payouts ont un match Qonto (RAS).
3. **Si `silence (aucun payout)` ou `silence (aucun CSV Qonto)`** : input manquant. Indique au founder ce qui manque.
4. **Si embed jaune** (orphan_credits ≥ 1) : ≥ 1 crédit Qonto Stripe sans payout matché. Souvent un virement test ou un export Stripe incomplet. Liste les crédits orphelins.
5. **Si embed rouge** (orphan_payouts ≥ 1) : Stripe a payé mais Qonto n'a pas reçu. URGENT — vérifier le compte Qonto direct (fonds bloqués ? swift en cours ? fraude ?).

## Notes

- Fenêtre de matching = J à J+5 jours (Stripe → Qonto met 1-3 jours ouvrés).
- Tolérance montant = 1 centime (arrondi compta).
- Algo glouton — chaque crédit Qonto est consommé au plus une fois.
- Pas de breaker dédié (c'est un audit, pas un kill switch).

## Voir aussi

- Code : [argos_ops/agents/reconcile_bot.py](../../argos_ops/agents/reconcile_bot.py)
- Helper : [argos_ops/finance/reconcile.py](../../argos_ops/finance/reconcile.py)
