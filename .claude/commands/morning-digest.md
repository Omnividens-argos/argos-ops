---
description: Lance le digest quotidien Argos Ops et le pousse sur Discord
---

# /morning-digest

Slash command Claude Code invoquée tous les matins par cron / Task Scheduler
(`0 8 * * *` Paris) **sur l'ordi du fondateur** (cf. D-017).

## Procédure

1. Lance le script `uv run python scripts/run_digest.py` (foreground, ~3-5 secondes).
2. Lis la sortie loguru et l'exit code.
3. **Si exit 0** :
   - Confirme que le digest est parti sur Discord
   - Si tu repères un signal qui mérite attention dans le `output_summary`
     (MRR baisse > 5 %, escalades en attente > 3, breakers actifs), écris en
     1-2 phrases ce que tu suggères au fondateur — sans noyer si tout va bien
4. **Si exit 1 (status=failed)** :
   - Lis l'erreur loggée
   - Vérifie d'abord les causes communes : `DISCORD_WEBHOOK_DIGEST`
     manquant dans `.env.local`, container `argos-postgres-local` arrêté
     (`docker ps`), webhook Discord 401/404 (à régénérer)
   - Propose la correction au fondateur, ne tente pas de fix automatique
5. **Si exit 1 (status=killed_by_breaker)** :
   - Le breaker `DigestBuilder` est tripé. Note le motif (`agent_runs.error`)
     et propose au fondateur de reset via le panel admin (P16) ou directement
     en SQL si urgent.

## Notes

- Le script logge déjà dans `agent_runs` (table Postgres) — pas besoin que
  tu reloggies. Garde tes commentaires courts (Discord est la source de
  vérité visuelle pour le fondateur).
- L'agent **n'envoie rien d'autre que le digest** : si tu identifies un
  vrai souci dans les KPIs, tu le mentionnes dans la conversation, mais tu
  **ne pushes pas un second message** sur Discord depuis cette commande.
- Convention de couleur de l'embed (lue dans le code) :
  - Vert : tout OK
  - Jaune : escalades à traiter humain en attente
  - Rouge : breaker actif

## Voir aussi

- Code : [`argos_ops/agents/digest_builder.py`](../../argos_ops/agents/digest_builder.py)
- Skill : [`.claude/skills/digest-builder/`](../skills/digest-builder/)
- Setup cron : voir le README du skill
- Décision archi : [`docs/DECISIONS.md` D-017](../../docs/DECISIONS.md)
