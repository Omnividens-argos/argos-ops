---
description: Lance TaxBot — drafte une TVA CA3 mensuelle + IS prévisionnel depuis Stripe MRR. Écrit data/finance/ca3_<YYYY-MM>.md (P22.F Sprint 10).
---

# /run-tax-prep

Slash command Claude Code invoquée manuellement vers le 15 du mois (avant la
date limite CA3 du 19) **sur l'ordi du fondateur** (D-017).

## Procédure

1. Lance `uv run python scripts/run_tax_bot.py` (foreground, ~5-15 s).
2. Lis la sortie loguru. Le draft est dans `data/finance/ca3_<YYYY-MM>.md`.
3. **Si exit 0** : `output_summary` = `ca_ht=X tva_collected=Y tva_deductible=Z tva_net=N`. Affiche-le au founder + le chemin du fichier généré.
4. Rappelle au founder qu'il doit :
   - Renseigner la TVA déductible (achats fournisseurs) manuellement avant dépôt
   - Auditer le draft avant de copier-coller sur impots.gouv.fr (date limite : 19 du mois M+1)
5. **Si exit 1** : `STRIPE_SECRET_KEY` manquant ou Stripe API erreur. Propose la correction.

## Notes

- Hypothèse : CA HT = MRR Stripe courant (proxy). C'est juste un draft, pas une compta certifiée.
- Taux 20 % par défaut (services SaaS BtoB France).
- IS prévisionnel uniquement si le founder fournit un `projected_annual_profit_eur` au constructeur (sinon section omise).
- **Pas de connexion DGFiP** — c'est de la pré-rédaction pour audit humain.

## Voir aussi

- Code : [argos_ops/agents/tax_bot.py](../../argos_ops/agents/tax_bot.py)
- Helpers TVA / IS : [argos_ops/finance/tva.py](../../argos_ops/finance/tva.py)