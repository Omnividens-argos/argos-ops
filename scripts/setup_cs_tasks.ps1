<#
.SYNOPSIS
  Idempotent setup des taches Task Scheduler Windows pour la famille
  Customer Success & Support (P22.G) : 8 bots cron + 1 bot reactif.

.DESCRIPTION
  Huit bots planifies :

  Cadence quotidienne :
  - argos-ops-onboarding        - quotidien 08:00  - drafts J+0/J+7/J+30
  - argos-ops-escalation-router - quotidien 08:30  - triage P0/P1/P2 + SLA
  - argos-ops-health-score      - quotidien 09:00  - score sante par compte
  - argos-ops-nps               - quotidien 09:15  - drafts NPS post-onboarding/renew
  - argos-ops-churn-predict     - quotidien 09:30  - signaux pre-churn
  - argos-ops-upsell-spots      - quotidien 09:45  - usage >= 80% quota

  Cadence hebdomadaire :
  - argos-ops-kb-updater        - lundi 10:00      - gaps KB depuis tickets

  Cadence mensuelle :
  - argos-ops-review-campaign   - 1er du mois 10:00 - drafts G2/Capterra J+30

  Reactif (slash + health-check) :
  - SupportBot : /run-support-tier1 (humain-in-the-loop + skill kb-rag)
    Le health-check passif compte les chunks KB indexes.

  Idempotent - relancer ecrase les taches existantes.

.EXAMPLE
  PS> .\scripts\setup_cs_tasks.ps1
  PS> .\scripts\setup_cs_tasks.ps1 -DryRun

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

function Register-CSTask {
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
# OnboardingBot - quotidien 08:00
# -----------------------------------------------------------------------------
$onboardingTrigger = New-ScheduledTaskTrigger -Daily -At "08:00"
Register-CSTask `
    -TaskName "argos-ops-onboarding" `
    -ScriptRelPath "scripts\run_onboarding_bot.py" `
    -Trigger $onboardingTrigger `
    -Description "OnboardingBot - drafts J+0/J+7/J+30 (P22.G), tous les jours 08:00"

# -----------------------------------------------------------------------------
# EscalationRouter - quotidien 08:30
# -----------------------------------------------------------------------------
$escalationTrigger = New-ScheduledTaskTrigger -Daily -At "08:30"
Register-CSTask `
    -TaskName "argos-ops-escalation-router" `
    -ScriptRelPath "scripts\run_escalation_router.py" `
    -Trigger $escalationTrigger `
    -Description "EscalationRouter - triage P0/P1/P2 + SLA (P22.G), tous les jours 08:30"

# -----------------------------------------------------------------------------
# HealthScoreBot - quotidien 09:00
# -----------------------------------------------------------------------------
$healthTrigger = New-ScheduledTaskTrigger -Daily -At "09:00"
Register-CSTask `
    -TaskName "argos-ops-health-score" `
    -ScriptRelPath "scripts\run_health_score.py" `
    -Trigger $healthTrigger `
    -Description "HealthScoreBot - score sante par compte (P22.G), tous les jours 09:00"

# -----------------------------------------------------------------------------
# NPSCollector - quotidien 09:15
# -----------------------------------------------------------------------------
$npsTrigger = New-ScheduledTaskTrigger -Daily -At "09:15"
Register-CSTask `
    -TaskName "argos-ops-nps" `
    -ScriptRelPath "scripts\run_nps_collector.py" `
    -Trigger $npsTrigger `
    -Description "NPSCollector - drafts NPS post-onboarding/renew (P22.G), tous les jours 09:15"

# -----------------------------------------------------------------------------
# ChurnPredictor - quotidien 09:30
# -----------------------------------------------------------------------------
$churnTrigger = New-ScheduledTaskTrigger -Daily -At "09:30"
Register-CSTask `
    -TaskName "argos-ops-churn-predict" `
    -ScriptRelPath "scripts\run_churn_predictor.py" `
    -Trigger $churnTrigger `
    -Description "ChurnPredictor - signaux pre-churn (P22.G), tous les jours 09:30"

# -----------------------------------------------------------------------------
# UpsellSpotter - quotidien 09:45
# -----------------------------------------------------------------------------
$upsellTrigger = New-ScheduledTaskTrigger -Daily -At "09:45"
Register-CSTask `
    -TaskName "argos-ops-upsell-spots" `
    -ScriptRelPath "scripts\run_upsell_spotter.py" `
    -Trigger $upsellTrigger `
    -Description "UpsellSpotter - usage >= 80% quota (P22.G), tous les jours 09:45"

# -----------------------------------------------------------------------------
# KBUpdater - hebdo lundi 10:00
# -----------------------------------------------------------------------------
$kbTrigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday -At "10:00"
Register-CSTask `
    -TaskName "argos-ops-kb-updater" `
    -ScriptRelPath "scripts\run_kb_updater.py" `
    -Trigger $kbTrigger `
    -Description "KBUpdater - gaps KB depuis tickets (P22.G), lundi 10:00"

# -----------------------------------------------------------------------------
# ReviewBot - mensuel le 1er a 10:00 (via XML CalendarTrigger)
# -----------------------------------------------------------------------------
$reviewTaskName = "argos-ops-review-campaign"
$reviewScriptRel = "scripts\run_review_bot.py"
$reviewAbsPath = Join-Path $RepoRoot $reviewScriptRel

Write-Host "=== $reviewTaskName ===" -ForegroundColor Cyan
Write-Host "  Script   : $reviewScriptRel"
Write-Host "  Trigger  : ReviewBot mensuel, 1er du mois 10:00"
Write-Host "  DryRun   : $($DryRun.IsPresent)"

if (-not (Test-Path $reviewAbsPath)) {
    Write-Error "Script introuvable : $reviewAbsPath"
    exit 1
}

$reviewXml = @"
<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.4" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Description>ReviewBot - drafts G2/Capterra J+30 (P22.G), 1er du mois 10:00</Description>
  </RegistrationInfo>
  <Triggers>
    <CalendarTrigger>
      <StartBoundary>2026-01-01T10:00:00</StartBoundary>
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
      <Arguments>run python $reviewScriptRel</Arguments>
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
    $existing = Get-ScheduledTask -TaskName $reviewTaskName -ErrorAction SilentlyContinue
    if ($existing) {
        Write-Host "[INFO] Tache existante detectee - sera remplacee." -ForegroundColor Yellow
        Unregister-ScheduledTask -TaskName $reviewTaskName -Confirm:$false
    }
    Register-ScheduledTask -TaskName $reviewTaskName -Xml $reviewXml | Out-Null
    Write-Host "[OK] Tache '$reviewTaskName' enregistree." -ForegroundColor Green
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
        -TaskName "argos-ops-onboarding", "argos-ops-escalation-router", `
                  "argos-ops-health-score", "argos-ops-nps", `
                  "argos-ops-churn-predict", "argos-ops-upsell-spots", `
                  "argos-ops-kb-updater", "argos-ops-review-campaign" `
        | Get-ScheduledTaskInfo `
        | Format-Table TaskName, LastRunTime, LastTaskResult, NextRunTime
}

Write-Host ""
Write-Host "[i] Pour tester immediatement (Docker requis) :"
Write-Host "    Start-ScheduledTask -TaskName 'argos-ops-escalation-router'"
Write-Host "    Start-ScheduledTask -TaskName 'argos-ops-health-score'"
Write-Host ""
Write-Host "[i] Bot reactif (slash + health-check) :"
Write-Host "    /run-support-tier1   (SupportBot)"
