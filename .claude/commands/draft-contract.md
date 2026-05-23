---
description: Lance ContractGenerator — génère le contrat CGV/MSA Markdown + PDF depuis le context.yaml d'un deal dont le devis est sent. Idempotent.
---

# /draft-contract

Slash command Claude Code invoquée manuellement après que le client a validé le devis **sur l'ordi du fondateur** (D-017).

## Procédure

1. Pré-requis : `data/proposals/<deal_id>/status.yaml` doit contenir `proposal_status: sent` (positionné à la main par le founder après envoi du devis).
2. Lance `uv run python scripts/run_contract_generator.py`.
3. **Si exit 0 et `drafted > 0`** : contrats créés dans `data/contracts/<deal_id>/contract.md` (et `.pdf` si pandoc dispo).
4. **Si exit 0 et `waiting_on_proposal > 0`** : il y a des deals avec context mais sans devis envoyé — flag normal, attendre que founder envoie les devis.

## Notes

- Source unique du context = `data/proposals/<deal_id>/context.yaml` (jamais dupliqué dans `data/contracts/`).
- Le contrat reprend : durée d'engagement, prix HT + TTC, remise éventuelle, articles RGPD/AI Act standards, signatures.
- Breaker associé : `ContractGenerator` (P15).
