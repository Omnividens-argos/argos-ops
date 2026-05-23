<#
.SYNOPSIS
  Idempotent setup de la Task Scheduler Windows ``argos-ops-bot-health``.

.DESCRIPTION
  Cron toutes les 2 h qui lance ``scripts/run_bot_health.py``
  (P22.B Meta-Ops core). Politique anti-spam : silence Discord si
  tout est vert, embed jaune/rouge sinon (webhook
  ``DISCORD_WEBHOOK_OPS_LOGS``).

  Pourquoi 2 h : EmailBot tourne toutes les 15 min sur la fenêtre
  8 h-22 h, donc un check toutes les 2 h détecte rapidement un
  Task Scheduler désactivé ou un agent qui tombe en erreur en
  rafale, sans saturer Discord.

  Le script est idempotent — relancer écrase la tâche existante.

.EXAMPLE
  PS> .\scripts\setup_bot_health_task.ps1
  Crée ou met à jour la tâche.

  PS> .\scripts\setup_bot_health_task.ps1 -DryRun
  Affiche ce qui serait fait, sans toucher au Task Scheduler.

.NOTES
  Lancer en PowerShell avec **autorisations admin** (clic droit →
  Exécuter en tant qu'administrateur), sinon ``Register-ScheduledTask``
  peut échouer sur certaines configs.

  D-017 — agent local sur l'ordi du fondateur, pas sur le serveur.
#>

[CmdletBinding()]
param(
    [switch] $DryRun
)

$ErrorActionPreference = "Stop"

$TaskName = "argos-ops-bot-health"
$RepoRoot = "C:\Users\pauzzle\Desktop\argos-ops"
$Description = "BotHealthBot toutes les 2h (P22.B) — uptime + erreurs récentes des bots actifs"

# uv direct (cf. pattern argos-ops-health-check) : script Python pur,
# pas un slash command — pas besoin de Claude Code en boucle.
$UvCommand = "uv"
$UvArgs = "run python scripts\run_bot_health.py"

Write-Host "=== Setup Task Scheduler ===" -ForegroundColor Cyan
Write-Host "  TaskName     : $TaskName"
Write-Host "  Cron         : toutes les 2h (offset +30min)"
Write-Host "  Command      : $UvCommand $UvArgs"
Write-Host "  WorkingDir   : $RepoRoot"
Write-Host "  DryRun       : $($DryRun.IsPresent)"
Write-Host ""

# Vérif rapide que le repo est bien là
if (-not (Test-Path "$RepoRoot\scripts\run_bot_health.py")) {
    Write-Error "scripts\run_bot_health.py introuvable dans $RepoRoot — vérifie le chemin."
    exit 1
}

# Unregister si existe (idempotent)
$existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($existing) {
    Write-Host "[INFO] Tâche existante détectée — sera remplacée." -ForegroundColor Yellow
    if (-not $DryRun) {
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:`$false
    }
}

$action = New-ScheduledTaskAction `
    -Execute $UvCommand `
    -Argument $UvArgs `
    -WorkingDirectory $RepoRoot

# Toutes les 2 h, offset +30 min pour ne pas overlap avec EmailBot
# (qui tourne au quart d'heure pile). Démarre à 00:30, répète
# indéfiniment.
$startTime = (Get-Date).Date.AddMinutes(30)
$trigger = New-ScheduledTaskTrigger -Once -At $startTime `
    -RepetitionInterval (New-TimeSpan -Hours 2) `
    -RepetitionDuration (New-TimeSpan -Days 365)

# StartWhenAvailable = si le PC était éteint, lance dès qu'il
# se réveille. AllowStartIfOnBatteries pour ne pas skip si laptop
# débranché (le check est léger, < 3 sec).
$settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -DontStopIfGoingOnBatteries `
    -AllowStartIfOnBatteries `
    -RunOnlyIfNetworkAvailable

if ($DryRun) {
    Write-Host "[DRY-RUN] Tâche prête à enregistrer (rien envoyé)." -ForegroundColor Green
    exit 0
}

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Description $Description | Out-Null

Write-Host "[OK] Tâche '$TaskName' enregistrée." -ForegroundColor Green

# Vérification
Write-Host ""
Write-Host "=== État actuel ===" -ForegroundColor Cyan
Get-ScheduledTask -TaskName $TaskName | Get-ScheduledTaskInfo | Format-List `
    LastRunTime, LastTaskResult, NextRunTime, NumberOfMissedRuns

Write-Host ""
Write-Host "[i] Pour tester immédiatement :"
Write-Host "    Start-ScheduledTask -TaskName '$TaskName'"
