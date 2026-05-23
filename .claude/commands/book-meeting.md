---
description: Lance MeetingBooker — drafte email de confirmation + invitation iCalendar (.ics) pour chaque demande de RDV pending dans data/sales/meetings/requests.yaml.
---

# /book-meeting

Slash command Claude Code invoquée manuellement ou par Task Scheduler (`argos-ops-meeting-booker`, cadence horaire ouvrée 8h-19h Paris) **sur l'ordi du fondateur** (D-017).

## Procédure

1. Lance `uv run python scripts/run_meeting_booker.py`.
2. **Si exit 0 et `silence (no requests)`** : YAML absent. Le fondateur peut ajouter une demande à la main ou laisser EmailBot/CRM remplir.
3. **Si exit 0 et `drafted > 0`** : drafts créés dans `data/sales/meetings/drafts/<id>.md` avec attachment `.ics` joint. Propose au founder de lire les drafts et envoyer via `zimbra-ops` (drag-and-drop le `.ics` en pièce jointe).
4. **Si exit 0 et `drafted=0 already_done=N`** : tout est traité (les demandes déjà draftées passent en `status: drafted`).

## Notes

- Format `data/sales/meetings/requests.yaml` :
  ```yaml
  requests:
    - request_id: "acme-marc-2026-06-04"
      attendee_email: "marc@acme.fr"
      attendee_name: "Marc Dupont"
      company: "Acme SA"
      starts_at: "2026-06-04T14:00:00+00:00"
      duration_minutes: 30
      location: "Visio (Jitsi — lien envoyé H-2)"
      status: pending
  ```
- `starts_at` doit inclure une timezone (sinon UTC assumé).
- Le `.ics` généré est RFC 5545 — Outlook, Apple Mail, Gmail acceptent.
- Aucun envoi automatique — humain-in-the-loop strict.
- Breaker associé : `MeetingBooker` (P15).
