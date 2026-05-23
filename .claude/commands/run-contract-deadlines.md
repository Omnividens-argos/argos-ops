---
description: Lance ContractDeadlineBot — alerte 60j avant chaque renouvellement de contrat client
---

# /run-contract-deadlines

## Procédure

1. Lance `uv run python scripts/run_contract_deadlines.py`.
2. Lis `output_summary`.
3. **Si `silence (vert)`** : aucun contrat dans la fenêtre 60j.
4. **Si `alert pushed` (YELLOW)** : ≥1 contrat dans la fenêtre 30-60j.
   - Préparer upsell / négociation
5. **Si `alert pushed` (RED)** : ≥1 contrat dans la fenêtre < 30j (urgent).
   - Notifier la résiliation si nécessaire pour casser la tacite reconduction
   - Sinon préparer le renouvellement

## Notes

- Source : `data/contracts/clients.yaml` (format dans le code)
- Fenêtres : 60j = warn (jaune), 30j = urgent (rouge), 0 = expired
- Tacite reconduction Code de la consommation : préavis 3 mois avant échéance
