<#
.SYNOPSIS
  Idempotent setup de la Task Scheduler Windows ``argos-ops-health-check``.

.DESCRIPTION
  Cron quotidien 5h45 (TZ Paris implicite, l'horloge système doit l'être)
  qui lance ``scripts/health_check.py`` (P19). Push une notif Discord
  via ``DISCORD_WEBHOOK_OPS_LOGS`` si overall != green.

  Pourquoi 5h45 : juste avant le digest 8h, pour catch les régressions
  overnight et donner au fondateur une notif Discord avant son café.

  Le script est idempotent — relancer écrase la tâche existante sans
  poser de question.

.EXAMPLE
  PS> .\scripts\setup_health_check_task.ps1
  Crée ou met à jour la tâche.

  PS> .\scripts\setup_health_check_task.ps1 -DryRun
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

$TaskName = "argos-ops-health-check"
$RepoRoot = "C:\Users\pauzzle\Desktop\argos-ops"
$Description = "Health check quotidien Argos Ops (P19) — DB / KB / agents freshness / breakers / queued"

# uv direct (cf. pattern argos-ops-email-bot dans skill zimbra-ops) :
# on évite l'invocation claude CLI car health_check est un script Python
# pur, pas un slash command — pas besoin de Claude Code en boucle.
$UvCommand = "uv"
$UvArgs = "run python scripts\health_check.py"

# 5h45 Paris (horloge système). Choix justifié dans le module
# argos_ops/health.py docstring : juste avant le digest 8h.
$TriggerTime = "05:45"

Write-Host "=== Setup Task Scheduler ===" -ForegroundColor Cyan
Write-Host "  TaskName     : $TaskName"
Write-Host "  Cron         : daily @ $TriggerTime (Paris implicite)"
Write-Host "  Command      : $UvCommand $UvArgs"
Write-Host "  WorkingDir   : $RepoRoot"
Write-Host "  DryRun       : $($DryRun.IsPresent)"
Write-Host ""

# Vérif rapide que le repo est bien là
if (-not (Test-Path "$RepoRoot\scripts\health_check.py")) {
    Write-Error "scripts\health_check.py introuvable dans $RepoRoot — vérifie le chemin."
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

$trigger = New-ScheduledTaskTrigger -Daily -At $TriggerTime

# StartWhenAvailable = si le PC était éteint à 5h45, lance dès qu'il
# se réveille. AllowStartIfOnBatteries pour ne pas skip si laptop
# débranché (le check est léger, < 5 sec).
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

# Mode silencieux : aucune fenetre console au declenchement du cron.
# Principal S4U = la tache tourne dans la session 0 (non-interactive).
# cf. scripts\make_tasks_silent.ps1
$silentPrincipal = New-ScheduledTaskPrincipal `
    -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType S4U -RunLevel Limited
Set-ScheduledTask -TaskName $TaskName -Principal $silentPrincipal | Out-Null

Write-Host "[OK] Tâche '$TaskName' enregistrée." -ForegroundColor Green

# Vérification
Write-Host ""
Write-Host "=== État actuel ===" -ForegroundColor Cyan
Get-ScheduledTask -TaskName $TaskName | Get-ScheduledTaskInfo | Format-List `
    LastRunTime, LastTaskResult, NextRunTime, NumberOfMissedRuns

Write-Host ""
Write-Host "[i] Pour tester immédiatement :"
Write-Host "    Start-ScheduledTask -TaskName '$TaskName'"
Write-Host ""
Write-Host "[i] Pour voir les logs (Event Viewer) :"
Write-Host "    Get-WinEvent -LogName 'Microsoft-Windows-TaskScheduler/Operational' \"
Write-Host "      -MaxEvents 20 | Where-Object {`$_.Message -like '*$TaskName*'}"
