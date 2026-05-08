---
name: digest-builder
description: Construit le digest quotidien Argos Ops (KPIs des dernières 24 h) à partir de Postgres et le pousse sur Discord. Utilise ce skill quand le user demande de lancer ou de modifier le digest matinal, d'ajouter une métrique au digest, ou de débugger pourquoi le digest n'est pas parti.
---

# digest-builder

Skill technique pour le premier agent Argos Ops — encapsule la logique
« lire les KPIs des dernières 24 h dans Postgres + formater + pousser
Discord ». Réutilisable par AnalyticsBot (futur, P19) qui produira des
digests à cadence différente (hebdomadaire / mensuelle).

## Inputs (variables d'environnement)

| Variable | Source | Requise ? |
|---|---|---|
| `DATABASE_URL` | `.env.local` | Oui (sinon l'agent ne peut pas lire les KPIs) |
| `DISCORD_WEBHOOK_DIGEST` | `.env.local` (P1.B) | Oui (sinon l'agent renvoie status=failed) |

## Outputs

- **Embed Discord** sur le webhook digest (titre, fields MRR / Leads / Customers / Tickets / Breakers, couleur selon état)
- **Ligne `agent_runs`** dans Postgres avec `agent_name='DigestBuilder'`, `status` ∈ {success, failed, killed_by_breaker}, `output_summary` contient un résumé court des KPIs
- **Exit code** 0 si success, 1 sinon

## Comment l'invoquer

### En CLI direct (pour dev / test)

```bash
uv run python scripts/run_digest.py
```

### Via slash command Claude Code (production)

```bash
claude --print "/morning-digest"
```

### Via cron / Task Scheduler (production schedule)

Cf. section « Setup cron » plus bas. La cadence canonique est `0 8 * * *`
(8 h Paris).

## Setup cron — Windows Task Scheduler

Argos Ops tourne sur l'ordi du fondateur (D-017). Sur Windows, on utilise
**Task Scheduler** (Planificateur de tâches).

### Création de la tâche (UI)

1. Ouvrir « Planificateur de tâches » (Win+R → `taskschd.msc`)
2. Action → « Créer une tâche... » (pas « Créer une tâche de base », on
   veut les options avancées)
3. Onglet **Général** :
   - Nom : `argos-ops-morning-digest`
   - Description : `Digest quotidien Argos Ops — D-017 cron sur ordi fondateur`
   - Cocher **« Exécuter avec les autorisations maximales »** (sinon
     `claude` CLI peut ne pas trouver le PATH)
4. Onglet **Déclencheurs** → Nouveau :
   - Lancer la tâche : Selon une planification
   - Quotidienne, début 08:00:00, récurrence 1 jour
5. Onglet **Actions** → Nouveau :
   - Action : Démarrer un programme
   - Programme : `claude` (ou chemin complet du `.exe` Claude Code si pas dans PATH)
   - Arguments : `--print "/morning-digest"`
   - Démarrer dans : `C:\Users\pauzzle\Desktop\argos-ops`
6. Onglet **Conditions** :
   - Décocher « Démarrer la tâche uniquement si l'ordinateur est sur secteur »
     (laptop sur batterie OK)
7. Onglet **Paramètres** :
   - Cocher « Exécuter la tâche dès que possible si une exécution
     planifiée a été manquée » (ordi éteint à 8 h → digest envoyé au réveil)
   - « Si la tâche est déjà en cours, alors la règle suivante s'applique :
     ne pas démarrer une nouvelle instance »

### Création de la tâche (PowerShell — alternative scriptable)

```powershell
$action = New-ScheduledTaskAction -Execute "claude" `
  -Argument '--print "/morning-digest"' `
  -WorkingDirectory "C:\Users\pauzzle\Desktop\argos-ops"
$trigger = New-ScheduledTaskTrigger -Daily -At 08:00
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable `
  -DontStopIfGoingOnBatteries -AllowStartIfOnBatteries
Register-ScheduledTask -TaskName "argos-ops-morning-digest" `
  -Action $action -Trigger $trigger -Settings $settings `
  -Description "Digest quotidien Argos Ops — D-017"
```

### Vérification

```powershell
Get-ScheduledTask -TaskName "argos-ops-morning-digest" | Get-ScheduledTaskInfo
```

Pour tester immédiatement :

```powershell
Start-ScheduledTask -TaskName "argos-ops-morning-digest"
```

## Setup cron — Linux / WSL2 (alternative)

Si tu préfères WSL2 :

```bash
crontab -e
# Ajouter cette ligne :
0 8 * * * cd /mnt/c/Users/pauzzle/Desktop/argos-ops && claude --print "/morning-digest"
```

## Tests

Cf. `tests/test_digest_builder.py` :

- `test_build_digest_embed_green` — embed vert quand 0 escalade / 0 breaker
- `test_build_digest_embed_yellow` — embed jaune quand pending_human > 0
- `test_build_digest_embed_red` — embed rouge quand breaker actif
- `test_build_digest_embed_mrr_unbranched` — affiche « Stripe non branché » avant P7
- `test_format_leads_breakdown_empty` — affiche « 0 » quand aucun lead
- `test_format_leads_breakdown_multi_source` — ventilation triée par volume

## Métriques de succès

- **Latence** : < 5 s (P95 attendu ~2 s)
- **Taux de succès** : > 98 % (échec dominant attendu = `DISCORD_WEBHOOK_*`
  régénéré sans mise à jour `.env.local`)
- **Coût Claude Code** : ~negligible (le slash command lit la sortie d'un
  script Python, pas de LLM lourd ; consomme < 1 k tokens du forfait Pro Max
  par run)

## Limites connues

- **MRR placeholder** : la métrique MRR est marquée « Stripe non branché »
  jusqu'à P7 (FinanceBot). C'est volontaire — pas de placeholder hallucinant
- **CAC** : pas dans le digest pour l'instant (pas de pub active avant P12
  AdBot ; calculer un CAC à 0 € ne sert à rien). À ajouter en P12
- **Pas de comparatif S-1** sur le delta MRR jusqu'à P7 + 7 jours d'historique
