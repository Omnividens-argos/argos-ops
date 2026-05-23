---
description: Lance ReleaseNotesBot — drafte des release notes user-friendly par version depuis data/release_notes/spec.yaml. Humain peaufine et publie après claude-judge.
---

# /draft-release-notes

Slash command Claude Code invoquée manuellement (à chaque release client-visible).

## Procédure

1. Édite `data/release_notes/spec.yaml` (founder) avec les highlights, improvements, fixes, breaking_changes par version (`status: pending`).
2. Lance `uv run python scripts/run_release_notes.py`.
3. **Si `silence (no releases)`** : spec absente ou vide.
4. **Si `drafted > 0`** : Discord jaune. Pour chaque `data/public/release_notes/<version>.md` :
   - Audit `claude-judge` (tone user-friendly, anti-jargon, anti-bullet-fest).
   - Publie sur le site (Hugo / Markdown) ou newsletter.
5. Le bot patche `status: drafted` dans `spec.yaml` après création (idempotent).

## Notes

- Format `data/release_notes/spec.yaml` :
  ```yaml
  releases:
    - version: "v0.7"
      date: "2026-06-01"
      highlights:
        - "Le scanner détecte 3 nouvelles classes de vulnérabilités."
      improvements:
        - "Temps de scan moyen divisé par 2 sur les domaines > 50 pages."
      fixes:
        - "Les rapports ne plantaient plus en cas de SSL invalide."
      breaking_changes: []
      status: pending
  ```
- Tone systématique : focus utilisateur (pas de jargon technique), pas de commit SHA.
- Idempotent : draft existant non recréé.
- Skill complémentaire : `claude-judge` (P14) pour audit avant publication.
- Breaker : `ReleaseNotesBot` (P15).
