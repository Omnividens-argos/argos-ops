---
description: Lance DemoFollowupBot — drafte le mail récap post-démo (pain points + next steps + attachments) depuis data/sales/demos/done.yaml.
---

# /draft-demo-followup

Slash command Claude Code invoquée manuellement après chaque démo (humain-in-the-loop) **sur l'ordi du fondateur** (D-017).

## Procédure

1. Le fondateur ajoute une entrée dans `data/sales/demos/done.yaml` (pain points, next steps, attachments) immédiatement après la démo.
2. Lance `uv run python scripts/run_demo_followup.py`.
3. **Si exit 0 et `drafted > 0`** : drafts créés dans `data/sales/demos/drafts/<demo_id>.md`. Propose au founder de relire et envoyer via `zimbra-ops`.
4. Le YAML est patché avec `status: drafted` — idempotent (re-lancer ne re-drafte pas).

## Notes

- Format `data/sales/demos/done.yaml` :
  ```yaml
  demos:
    - demo_id: "acme-2026-05-23"
      first_name: "Marc"
      contact_email: "marc@acme.fr"
      when: 2026-05-23
      pain_points:
        - "Audit RGPD passé en panique au S2 dernier"
        - "Pas de visibilité scans entre 2 audits annuels"
      next_steps:
        - ["Argos", "Envoyer devis Pro 14j d'essai sous 48h"]
        - ["Marc", "Faire valider budget à son board"]
      attachments: ["devis-pro-acme.pdf"]
      focus_topic: "intégration GitLab CI"
      next_milestone: "vendredi prochain"
      status: pending
  ```
- `next_steps` doit être une liste de `[owner, action]` (2 éléments par step).
- Breaker associé : `DemoFollowupBot` (P15).
