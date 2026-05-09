---
description: Lance EmailBot inbound — pull IMAP, ingestion CRM, notif Discord
---

# /run-email-bot

Slash command Claude Code invoquée toutes les 15 min par cron / Task
Scheduler **sur l'ordi du fondateur** (cf. D-017). Pull les emails non lus
de `contact@omnividens.fr`, les logge dans le CRM et notifie Discord.

> **Pas de drafting ici.** Le drafting des réponses se fait via
> `/check-emails` (humain-in-the-loop). Ce slash command est purement
> mécanique : pull IMAP → log DB → marque lu → notif.

## Procédure

1. Lance le script `uv run python scripts/run_email_bot.py` (foreground, ~5-15 s
   selon le nombre d'emails).
2. Lis la sortie loguru et l'exit code.
3. **Si exit 0 (status=success)** :
   - Confirme le nombre d'emails ingérés (présent dans `output_summary`)
   - Si ≥ 1 email ingéré, suggère au fondateur de lancer `/check-emails`
     pour drafter les réponses
4. **Si exit 1 (status=failed)** :
   - Causes communes : `EMAIL_USER` ou `EMAIL_PASSWORD` manquant dans
     `.env.local` (D-005 pas finalisé), creds Zimbra invalides, hôte IMAP
     OVH temporairement injoignable
   - Propose la correction au fondateur, ne tente pas de fix automatique
5. **Si exit 1 (status=killed_by_breaker)** :
   - Le breaker `EmailBot` est tripé. Note le motif (`agent_runs.error`)
     et propose au fondateur de reset

## Notes

- Le script logge déjà dans `agent_runs` — pas besoin que tu reloggies
- L'agent **n'envoie aucun email** : seulement de l'ingestion. Si tu vois
  un envoi, c'est un bug
- L'agent skip automatiquement les expéditeurs `noreply@` / `mailer-daemon@` /
  `bounces@` (cf. `is_noreply` dans `argos_ops/integrations/zimbra.py`)
- Convention de couleur de l'embed Discord :
  - Vert : 0 emails (boîte vide)
  - Jaune : ≥ 1 email ingéré (action humaine requise)

## Voir aussi

- Code : [`argos_ops/agents/email_bot.py`](../../argos_ops/agents/email_bot.py)
- Wrapper : [`argos_ops/integrations/zimbra.py`](../../argos_ops/integrations/zimbra.py)
- Skill : [`.claude/skills/zimbra-ops/`](../skills/zimbra-ops/)
- Décisions : [D-017](../../docs/DECISIONS.md) (local-first), [D-018](../../docs/DECISIONS.md) (OVH Zimbra)
