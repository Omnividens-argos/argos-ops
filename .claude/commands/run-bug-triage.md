---
description: Lance BugTriageBot — classifie les issues GitHub par sévérité (P0/P1/P2) et suggère un label. Read-only — humain applique via gh issue edit.
---

# /run-bug-triage

Slash command Claude Code invoquée manuellement ou Task Scheduler (`argos-ops-triage`, hebdo).

## Procédure

1. (Optionnel) Rafraîchis `data/issues/open.yaml` :
   ```bash
   gh issue list --json number,title,body,labels,createdAt --state open \
     | jq '{issues: [.[] | {number, title, body, labels: [.labels[].name], opened_at: .createdAt}]}' \
     | yq -P > data/issues/open.yaml
   ```
2. Lance `uv run python scripts/run_bug_triage.py`.
3. **Si `silence (no issues)`** : fichier absent ou vide.
4. **Si `p0 > 0`** : Discord rouge, action immédiate. **Si `p1 > 0`** : orange.
5. Lis `data/issues/triage_<date>.yaml` et applique les labels suggérés :
   ```bash
   gh issue edit <num> --add-label "severity/critical"
   ```

## Notes

- Sévérité par mots-clés titre+body+labels (`argos_ops/agents/bug_triage.py`) :
  - P0 — "prod down", "data loss", "security", "vulnérabilité", "rce", "csrf", "xss", "sql injection"
  - P1 — "bug", "crash", "error 500", "regression", "broken"
  - P2 — sinon
- Labels suggérés : `severity/critical`, `severity/major`, `severity/minor`.
- Read-only : le bot NE modifie PAS les issues GitHub. Le founder applique les labels à la main (audit explicite).
- Idempotent : snapshot du jour écrasé.
- Breaker : `BugTriageBot` (P15).
