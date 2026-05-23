---
description: Lance EscalationRouter — classifie tickets en P0/P1/P2 (mots-clés sujet+body), calcule SLA réponse, flag les SLA breach. Discord rouge si breach.
---

# /run-ticket-triage

Slash command Claude Code invoquée manuellement (avant d'ouvrir le support du matin) ou par Task Scheduler (`argos-ops-triage`, toutes les 4h).

## Procédure

1. Lance `uv run python scripts/run_escalation_router.py`.
2. **Si exit 0 et `silence (no tickets)`** : `data/support/tickets.yaml` absent ou vide.
3. **Si `breached > 0`** : Discord rouge → traiter en priorité ces tickets.
4. **Si `p0 > 0 ou p1 > 0`** : Discord jaune → focus du jour.
5. **Si que des P2** : silence Discord, snapshot écrit pour audit.

## Notes

- Classification (cf. `argos_ops/cs/scoring.py`) :
  - P0 — mots-clés "prod down", "data loss", "urgent" (incident bloquant)
  - P1 — "bug", "error 500", "crash", "régression" (bug majeur)
  - P2 — sinon (question / amélioration)
  - Override manuel possible via `priority: "P0"` dans le YAML.
- SLA réponse :
  - P0 : 1h (Enterprise : 1h)
  - P1 : 4h (Enterprise : 2h)
  - P2 : 24h
- Cohérent avec `docs/ESCALATION_RULES.md`.
- Snapshot quotidien dans `data/support/triage_<date>.yaml` (audit + retrofit dashboards).
- Read-only sur les tickets — ne modifie jamais le YAML source.
- Breaker : `EscalationRouter` (P15).
