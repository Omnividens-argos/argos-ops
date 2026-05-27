<#
.SYNOPSIS
  Idempotent setup des taches Task Scheduler Windows pour la famille
  Produit & R&D (P22.J) : 4 bots cron + 1 bot reactif.

.DESCRIPTION
  Quatre bots planifies :

  Cadence quotidienne :
  - argos-ops-bug-triage      - quotidien 10:00 - trie issues P0/P1/P2

  Cadence hebdomadaire :
  - argos-ops-feedback-digest - lundi 11:00     - agrege demandes par theme
  - argos-ops-changelog       - lundi 11:30     - changelog depuis git log

  Cadence mensuelle :
  - argos-ops-roadmap         - 1er du mois 11:00 - publie roadmap publique

  Reactif (slash only) :
  - ReleaseNotesBot : /draft-release-notes (lance a la demande par sprint/version)

  Idempotent - relancer ecrase les taches existantes.

.EXAMPLE
  PS> .\scripts\setup_product_tasks.ps1
  PS> .\scripts\setup_product_tasks.ps1 -DryRun

.NOTES
  Lancer en PowerShell admin. Docker container argos-postgres-local UP.
  D-017 - bots locaux sur l'ordi du fondateur.
#>

[CmdletBinding()]
param(
    [switch] $DryRun
)

$ErrorActionPreference = "Stop"

$RepoRoot = "C:\Users\pauzzle\Desktop\argos-ops"
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

function Register-ProductTask {
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
# BugTriageBot - quotidien 10:00
# -----------------------------------------------------------------------------
$bugTriageTrigger = New-ScheduledTaskTrigger -Daily -At "10:00"
Register-ProductTask `
    -TaskName "argos-ops-bug-triage" `
    -ScriptRelPath "scripts\run_bug_triage.py" `
    -Trigger $bugTriageTrigger `
    -Description "BugTriageBot - trie issues P0/P1/P2 (P22.J), tous les jours 10:00"

# -----------------------------------------------------------------------------
# FeedbackAggregator - hebdo lundi 11:00
# -----------------------------------------------------------------------------
$feedbackTrigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday -At "11:00"
Register-ProductTask `
    -TaskName "argos-ops-feedback-digest" `
    -ScriptRelPath "scripts\run_feedback_aggregator.py" `
    -Trigger $feedbackTrigger `
    -Description "FeedbackAggregator - agrege demandes par theme (P22.J), lundi 11:00"

# -----------------------------------------------------------------------------
# ChangelogBot - hebdo lundi 11:30
# -----------------------------------------------------------------------------
$changelogTrigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday -At "11:30"
Register-ProductTask `
    -TaskName "argos-ops-changelog" `
    -ScriptRelPath "scripts\run_changelog_bot.py" `
    -Trigger $changelogTrigger `
    -Description "ChangelogBot - changelog depuis git log (P22.J), lundi 11:30"

# -----------------------------------------------------------------------------
# RoadmapPublisher - mensuel le 1er a 11:00 (via XML CalendarTrigger)
# -----------------------------------------------------------------------------
$roadmapTaskName = "argos-ops-roadmap"
$roadmapScriptRel = "scripts\run_roadmap_publisher.py"
$roadmapAbsPath = Join-Path $RepoRoot $roadmapScriptRel

Write-Host "=== $roadmapTaskName ===" -ForegroundColor Cyan
Write-Host "  Script   : $roadmapScriptRel"
Write-Host "  Trigger  : RoadmapPublisher mensuel, 1er du mois 11:00"
Write-Host "  DryRun   : $($DryRun.IsPresent)"

if (-not (Test-Path $roadmapAbsPath)) {
    Write-Error "Script introuvable : $roadmapAbsPath"
    exit 1
}

$roadmapXml = @"
<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.4" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Description>RoadmapPublisher - publie roadmap publique (P22.J), 1er du mois 11:00</Description>
  </RegistrationInfo>
  <Triggers>
    <CalendarTrigger>
      <StartBoundary>2026-01-01T11:00:00</StartBoundary>
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
      <Arguments>run python $roadmapScriptRel</Arguments>
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
    $existing = Get-ScheduledTask -TaskName $roadmapTaskName -ErrorAction SilentlyContinue
    if ($existing) {
        Write-Host "[INFO] Tache existante detectee - sera remplacee." -ForegroundColor Yellow
        Unregister-ScheduledTask -TaskName $roadmapTaskName -Confirm:$false
    }
    Register-ScheduledTask -TaskName $roadmapTaskName -Xml $roadmapXml | Out-Null
    Write-Host "[OK] Tache '$roadmapTaskName' enregistree." -ForegroundColor Green
    Write-Host ""
}

# -----------------------------------------------------------------------------
# Recap
# -----------------------------------------------------------------------------
if (-not $DryRun) {
    Write-Host "=== Recap ===" -ForegroundColor Cyan
    Get-ScheduledTask `
        -TaskName "argos-ops-bug-triage", "argos-ops-feedback-digest", `
                  "argos-ops-changelog", "argos-ops-roadmap" `
        | Get-ScheduledTaskInfo `
        | Format-Table TaskName, LastRunTime, LastTaskResult, NextRunTime
}

Write-Host ""
Write-Host "[i] Pour tester immediatement (Docker requis) :"
Write-Host "    Start-ScheduledTask -TaskName 'argos-ops-bug-triage'"
Write-Host "    Start-ScheduledTask -TaskName 'argos-ops-feedback-digest'"
Write-Host ""
Write-Host "[i] Bot reactif (slash only) :"
Write-Host "    /draft-release-notes   (ReleaseNotesBot)"
