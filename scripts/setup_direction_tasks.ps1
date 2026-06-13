<#
.SYNOPSIS
  Idempotent setup des taches Task Scheduler Windows pour la famille
  Direction & Strategie (P22.E) : StrategyBot, OKRTracker, BoardReporter.

.DESCRIPTION
  Trois bots planifies :

  - argos-ops-strategy-digest  - lundi 08:00 (hebdo) - digest KPIs 7j
  - argos-ops-okr-review       - lundi 08:15 (hebdo) - review OKR trimestriels
  - argos-ops-board-pack       - 1er du mois 07:00 - board pack mensuel pandoc

  DecisionLogger est interactif (slash /log-decision) - pas de cron.

  Idempotent - relancer ecrase les taches existantes.

.EXAMPLE
  PS> .\scripts\setup_direction_tasks.ps1
  Cree ou met a jour les 3 taches.

  PS> .\scripts\setup_direction_tasks.ps1 -DryRun
  Affiche ce qui serait fait, sans toucher au Task Scheduler.

.NOTES
  Lancer en PowerShell avec autorisations admin, sinon
  Register-ScheduledTask peut echouer.

  D-017 - bots locaux sur l'ordi du fondateur.
#>

[CmdletBinding()]
param(
    [switch] $DryRun
)

$ErrorActionPreference = "Stop"

$RepoRoot = "C:\Users\pauzzle\Desktop\argos-ops"
# Path absolu requis : le Task Scheduler n'herite pas du PATH utilisateur
# quand il lance la tache (uv installe via `winget install astral-sh.uv` ou
# via le script officiel se trouve sous %USERPROFILE%\.local\bin).
$UvCommand = "$env:USERPROFILE\.local\bin\uv.exe"
if (-not (Test-Path $UvCommand)) {
    $UvCommand = (Get-Command uv -ErrorAction SilentlyContinue).Path
}
if (-not $UvCommand -or -not (Test-Path $UvCommand)) {
    Write-Error "uv introuvable - verifie l'installation (winget install astral-sh.uv)"
    exit 1
}
Write-Host "[i] uv resolu vers : $UvCommand" -ForegroundColor DarkGray

$commonSettings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -DontStopIfGoingOnBatteries `
    -AllowStartIfOnBatteries `
    -RunOnlyIfNetworkAvailable

function Register-DirectionTask {
    param(
        [Parameter(Mandatory)] [string] $TaskName,
        [Parameter(Mandatory)] [string] $ScriptRelPath,
        [Parameter(Mandatory)] $Trigger,
        [Parameter(Mandatory)] [string] $Description
    )

    Write-Host "=== $TaskName ===" -ForegroundColor Cyan
    Write-Host "  Script   : $ScriptRelPath"
    Write-Host "  Trigger  : $Description"
    Write-Host "  DryRun   : $($DryRun.IsPresent)"

    $absPath = Join-Path $RepoRoot $ScriptRelPath
    if (-not (Test-Path $absPath)) {
        Write-Error "Script introuvable : $absPath"
        exit 1
    }

    $existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if ($existing) {
        Write-Host "[INFO] Tache existante detectee - sera remplacee." -ForegroundColor Yellow
        if (-not $DryRun) {
            Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
        }
    }

    $action = New-ScheduledTaskAction `
        -Execute $UvCommand `
        -Argument "run python $ScriptRelPath" `
        -WorkingDirectory $RepoRoot

    if ($DryRun) {
        Write-Host "[DRY-RUN] OK." -ForegroundColor Green
        Write-Host ""
        return
    }

    Register-ScheduledTask `
        -TaskName $TaskName `
        -Action $action `
        -Trigger $Trigger `
        -Settings $commonSettings `
        -Description $Description | Out-Null

    Write-Host "[OK] Tache '$TaskName' enregistree." -ForegroundColor Green
    Write-Host ""
}

# -----------------------------------------------------------------------------
# StrategyBot - hebdo lundi 08:00
# -----------------------------------------------------------------------------
$strategyTrigger = New-ScheduledTaskTrigger `
    -Weekly `
    -DaysOfWeek Monday `
    -At "08:00"

Register-DirectionTask `
    -TaskName "argos-ops-strategy-digest" `
    -ScriptRelPath "scripts\run_strategy_bot.py" `
    -Trigger $strategyTrigger `
    -Description "StrategyBot - digest hebdo KPIs (P22.E Direction Sprint 9), lundi 08:00"

# -----------------------------------------------------------------------------
# OKRTracker - hebdo lundi 08:15 (decale 15 min pour ne pas overlap StrategyBot)
# -----------------------------------------------------------------------------
$okrTrigger = New-ScheduledTaskTrigger `
    -Weekly `
    -DaysOfWeek Monday `
    -At "08:15"

Register-DirectionTask `
    -TaskName "argos-ops-okr-review" `
    -ScriptRelPath "scripts\run_okr_tracker.py" `
    -Trigger $okrTrigger `
    -Description "OKRTracker - review OKR trimestriels (P22.E Direction Sprint 9), lundi 08:15"

# -----------------------------------------------------------------------------
# BoardReporter - mensuel le 1er a 07:00
# -----------------------------------------------------------------------------
# New-ScheduledTaskTrigger ne supporte pas le mensuel, et MSFT_TaskMonthlyTrigger
# expose des proprietes variables selon la version Windows. On enregistre la
# tache via XML qui supporte nativement CalendarTrigger / ScheduleByMonth.
$boardTaskName = "argos-ops-board-pack"
$boardScriptRel = "scripts\run_board_reporter.py"
$boardAbsPath = Join-Path $RepoRoot $boardScriptRel

Write-Host "=== $boardTaskName ===" -ForegroundColor Cyan
Write-Host "  Script   : $boardScriptRel"
Write-Host "  Trigger  : BoardReporter mensuel, 1er du mois 07:00"
Write-Host "  DryRun   : $($DryRun.IsPresent)"

if (-not (Test-Path $boardAbsPath)) {
    Write-Error "Script introuvable : $boardAbsPath"
    exit 1
}

$boardXml = @"
<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.4" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Description>BoardReporter - board pack mensuel (P22.E Direction Sprint 9), 1er du mois 07:00</Description>
  </RegistrationInfo>
  <Triggers>
    <CalendarTrigger>
      <StartBoundary>2026-01-01T07:00:00</StartBoundary>
      <Enabled>true</Enabled>
      <ScheduleByMonth>
        <DaysOfMonth><Day>1</Day></DaysOfMonth>
        <Months>
          <January /><February /><March /><April /><May /><June />
          <July /><August /><September /><October /><November /><December />
        </Months>
      </ScheduleByMonth>
    </CalendarTrigger>
  </Triggers>
  <Settings>
    <StartWhenAvailable>true</StartWhenAvailable>
    <RunOnlyIfNetworkAvailable>true</RunOnlyIfNetworkAvailable>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
  </Settings>
  <Actions>
    <Exec>
      <Command>$UvCommand</Command>
      <Arguments>run python $boardScriptRel</Arguments>
      <WorkingDirectory>$RepoRoot</WorkingDirectory>
    </Exec>
  </Actions>
</Task>
"@

if ($DryRun) {
    Write-Host "[DRY-RUN] OK." -ForegroundColor Green
    Write-Host ""
}
else {
    $existing = Get-ScheduledTask -TaskName $boardTaskName -ErrorAction SilentlyContinue
    if ($existing) {
        Write-Host "[INFO] Tache existante detectee - sera remplacee." -ForegroundColor Yellow
        Unregister-ScheduledTask -TaskName $boardTaskName -Confirm:$false
    }
    Register-ScheduledTask -TaskName $boardTaskName -Xml $boardXml | Out-Null
    Write-Host "[OK] Tache '$boardTaskName' enregistree." -ForegroundColor Green
    Write-Host ""
}

# -----------------------------------------------------------------------------
# Recap
# -----------------------------------------------------------------------------
# -----------------------------------------------------------------------------
# Mode silencieux : aucune fenetre console au declenchement du cron.
# Bascule chaque tache argos-ops-* en principal S4U (session 0, non-interactif).
# cf. scripts\make_tasks_silent.ps1
# -----------------------------------------------------------------------------
if (-not $DryRun) {
    $silentPrincipal = New-ScheduledTaskPrincipal `
        -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType S4U -RunLevel Limited
    foreach ($silentTask in @(Get-ScheduledTask -TaskName "argos-ops-*" -ErrorAction SilentlyContinue)) {
        if ([string]$silentTask.Principal.LogonType -ne "S4U") {
            Set-ScheduledTask -TaskName $silentTask.TaskName -Principal $silentPrincipal | Out-Null
        }
    }
    Write-Host "[i] Taches argos-ops-* passees en mode silencieux (S4U)." -ForegroundColor DarkGray
}

if (-not $DryRun) {
    Write-Host "=== Recap ===" -ForegroundColor Cyan
    Get-ScheduledTask `
        -TaskName "argos-ops-strategy-digest", "argos-ops-okr-review", "argos-ops-board-pack" `
        | Get-ScheduledTaskInfo `
        | Format-Table TaskName, LastRunTime, LastTaskResult, NextRunTime
}

Write-Host ""
Write-Host "[i] Pour tester immediatement :"
Write-Host "    Start-ScheduledTask -TaskName 'argos-ops-strategy-digest'"
Write-Host "    Start-ScheduledTask -TaskName 'argos-ops-okr-review'"
Write-Host "    Start-ScheduledTask -TaskName 'argos-ops-board-pack'"
