---
description: Lance ProposalBot — génère un devis Markdown + PDF (pandoc si dispo) depuis data/proposals/<deal_id>/context.yaml. Idempotent (skip si déjà drafté).
---

# /draft-proposal

Slash command Claude Code invoquée manuellement après validation d'un context devis **sur l'ordi du fondateur** (D-017).

## Procédure

1. Le fondateur crée `data/proposals/<deal_id>/context.yaml` à la main (variables compte + plan + prix).
2. Lance `uv run python scripts/run_proposal_bot.py`.
3. **Si exit 0 et `drafted > 0`** :
   - `data/proposals/<deal_id>/proposal.md` toujours présent.
   - `data/proposals/<deal_id>/proposal.pdf` si pandoc est sur le PATH (sinon `pdf_skipped_no_pandoc > 0` — convertir manuellement).
   - `data/proposals/<deal_id>/status.yaml` écrit avec `proposal_status: drafted`.
4. Quand le founder envoie le devis au client → éditer `status.yaml` à la main : `proposal_status: sent`. Cela débloque `/draft-contract` plus tard.

## Notes

- Format `data/proposals/<deal_id>/context.yaml` :
  ```yaml
  deal_id: "acme-q2-2026"
  company: "Acme SA"
  contact_name: "Marc Dupont"
  contact_email: "marc@acme.fr"
  siret: "12345678900012"  # optionnel
  plan: "Argos Pro"
  monthly_price_eur: 350
  setup_fee_eur: 500
  discount_percent: 10  # optionnel, défaut 0
  contract_duration_months: 12
  issue_date: 2026-05-23
  validity_days: 30
  ```
- PDF généré via `pandoc --pdf-engine=xelatex` (fallback sans engine si xelatex absent).
- Aucun envoi automatique — le fondateur joint le PDF dans Zimbra à la main.
- Breaker associé : `ProposalBot` (P15).