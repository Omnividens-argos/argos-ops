---
description: Lance OutboundBot — scaffold des séquences cold email depuis data/outbound/inbox/leads.csv (P13.A shadow mode). Aucun envoi tant que OUTBOUND_LIVE_MODE=false. Idempotent — re-lancer sur le même CSV ne dupliquera pas les séquences déjà scaffold.
---

# /run-outbound-bot

Slash command cron-friendly pour lancer l'agent `OutboundBot` (P13.A,
shadow mode). À programmer typiquement à 9h00 Paris en croisière, mais
aussi invocable à la demande après dépôt d'un CSV de leads.

## Préconditions

- `data/outbound/inbox/leads.csv` existe (sinon : run succès vide)
- `OUTBOUND_UNSUBSCRIBE_SECRET` configuré dans `.env.local` (obligatoire
  même en shadow — sert à pré-calculer les tokens d'opt-out HMAC)
- Breaker `OutboundBot` non tripped (vérifier via `/reset-breaker`)
- Breaker `outbound_volume_exceeded` non tripped (déclenché si l'avant-dernier
  run a refusé un CSV > `OUTBOUND_DAILY_MAX`)

## Procédure (pour Claude Code lors de l'invocation)

```python
from argos_ops.agents.base import run_agent
from argos_ops.agents.outbound_bot import OutboundBot

result = await run_agent(OutboundBot())
print(result.status, result.output_summary)
```

`run_agent()` applique automatiquement :

- Check breaker `OutboundBot` (kill switch global)
- Check toggle Admin Panel (`disabled` / `paused` / `daily_limit`)
- INSERT dans `agent_runs` (start + complete)
- Top-level exception catch

## Sortie attendue

- **Succès** : `output_summary="read=N new=K already=M failures=0"` + notif
  Discord avec liste des nouveaux slugs créés
- **Échec CSV invalide** : status=`failed`, `error="CSV invalide : ..."`
  (header manquant, domain malformé, etc.)
- **Échec volume** : status=`failed`, breaker `outbound_volume_exceeded`
  tripped, notif Discord. Audit `data/outbound/inbox/leads.csv` puis
  `/reset-breaker outbound_volume_exceeded`
- **Pas de CSV** : status=`success`, `output_summary="... (no csv)"`

## Cron prod (Task Scheduler / cron WSL2)

Cadence recommandée : quotidien 9h00 Paris.

```powershell
# PowerShell — à exécuter en admin une fois
$action = New-ScheduledTaskAction -Execute "uv" `
    -Argument "run python -m argos_ops.scripts.run_outbound_bot" `
    -WorkingDirectory "C:\Users\pauzzle\Desktop\argos-ops"
$trigger = New-ScheduledTaskTrigger -Daily -At 09:00
Register-ScheduledTask -TaskName "argos-ops-outbound-bot" `
    -Action $action -Trigger $trigger -RunLevel Highest
```

À enregistrer une fois P13.B (live mode) actif. Tant qu'on est en shadow,
le run manuel via `/run-outbound-bot` suffit.

## Suite logique

Une fois les séquences scaffold, pour chaque slug retourné :

```
/draft-outbound <slug>
```

(humain-in-the-loop — invoque `lead-enricher` + `outbound-personalizer`
+ rédige les bodies + audit `claude-judge` avant écriture)
