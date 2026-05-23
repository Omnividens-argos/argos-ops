---
description: Lance RGPDAuditor — scan PII collecte vs data/compliance/rgpd_registry.yaml
---

# /run-rgpd-audit

Slash Claude Code invoquée manuellement ou par Task Scheduler.

## Procédure

1. Lance `uv run python scripts/run_rgpd_auditor.py`.
2. Lis l'exit code et `output_summary`.
3. **Si `silence (vert)`** : tous les findings PII sont au registre.
4. **Si `alert pushed` (YELLOW)** : ≥1 finding non documenté.
   - Vérifier les fields cités dans l'embed
   - Soit ajouter le path au registre `data/compliance/rgpd_registry.yaml`
   - Soit retirer la collecte si elle n'est pas légitime
5. **Si `alert pushed` (RED)** : le registre est absent (faute professionnelle).
   Créer le fichier immédiatement.

## Notes

- Le scan est conservateur — préfère un faux positif (ajout au registre)
  qu'un faux négatif (collecte non documentée).
- Patterns matchés : `email`, `phone`, `ip_address`, `name`, `address`, `id_card`.
- Path préfixe dans le YAML : tout sous-chemin commençant par le préfixe est
  considéré couvert.