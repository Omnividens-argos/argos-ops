---
description: Lance UpsellSpotter — repère les comptes saturés (usage ≥ 80% quota plan) prêts pour upsell. Read-only, snapshot YAML + Discord si candidats.
---

# /run-upsell-spots

Slash command Claude Code invoquée manuellement ou par Task Scheduler (`argos-ops-upsell`, hebdo mardi 11h Paris).

## Procédure

1. Lance `uv run python scripts/run_upsell_spotter.py`.
2. **Si exit 0 et `silence (no customers)`** : pas de CRM CS encore.
3. **Si `upsell_candidates > 0`** : embed Discord jaune. Lis `data/upsell/candidates_<date>.yaml`, contacte chaque candidat par mail/call avec pitch upsell vers le plan supérieur.
4. **Si `upsell_candidates=0`** : silence.

## Notes

- Seuil : `USAGE_UPSELL_THRESHOLD = 0.80` (80% du quota plan, cf. `argos_ops/cs/scoring.py`).
- Plan supérieur suggéré :
  - starter → pro
  - pro → enterprise
  - enterprise → null (déjà au top — pas de suggestion)
- Plans enterprise (quota = 0 = sur mesure) sont automatiquement skip.
- Snapshot quotidien écrasé. Pas d'historique.
- Read-only sur `data/cs/customers.yaml`.
- Breaker : `UpsellSpotter` (P15).
