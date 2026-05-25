<#
.SYNOPSIS
  Idempotent setup des taches Task Scheduler Windows pour la famille
  Sales / Commercial (P22.H) : 5 bots cron + 4 bots reactifs (slash only).

.DESCRIPTION
  Cinq bots planifies (cron quotidien / hebdo) :

  - argos-ops-prospect-mining   - quotidien 07:00      - sources publiques RSS
  - argos-ops-lead-enrich       - quotidien 07:15      - BANT + persona + email guess
  - argos-ops-intent-signals    - quotidien 08:00      - breaches / CISO hires / fundraise
  - argos-ops-outbound          - quotidien 09:00      - scaffold sequences (shadow)
  - argos-ops-deal-scoring      - lundi 08:30 (hebdo)  - score pipe + flag stalled

  Quatre bots reactifs (slash only, pas de cron — declenches a la demande
  par le founder via /book-meeting, /draft-demo-followup, /draft-proposal,
  /draft-contract) : MeetingBooker, DemoFollowupBot, ProposalBot,
  ContractGenerator. Pas enregistres dans Task Scheduler.

  Idempotent - relancer ecrase les taches existantes.

.EXAMPLE
  PS> .\scripts\setup_sales_tasks.ps1
  Cree ou met a jour les 5 taches cron.

  PS> .\scripts\setup_sales_tasks.ps1 -DryRun
  Affiche ce qui serait fait, sans toucher au Task Scheduler.

.NOTES
  Lancer en PowerShell avec autorisations admin. Docker container
  argos-postgres-local doit tourner pour que les runs aboutissent.
  OutboundBot reste shadow tant que OUTBOUND_LIVE_MODE=false dans .env.local.
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

function Register-SalesTask {
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
# ProspectMiner - quotidien 07:00
# -----------------------------------------------------------------------------
$prospectTrigger = New-ScheduledTaskTrigger -Daily -At "07:00"
Register-SalesTask `
    -TaskName "argos-ops-prospect-mining" `
    -ScriptRelPath "scripts\run_prospect_miner.py" `
    -Trigger $prospectTrigger `
    -Description "ProspectMiner - sources publiques RSS (P22.H), tous les jours 07:00"

# -----------------------------------------------------------------------------
# LeadEnricher - quotidien 07:15 (apres ProspectMiner)
# -----------------------------------------------------------------------------
$enrichTrigger = New-ScheduledTaskTrigger -Daily -At "07:15"
Register-SalesTask `
    -TaskName "argos-ops-lead-enrich" `
    -ScriptRelPath "scripts\run_lead_enricher.py" `
    -Trigger $enrichTrigger `
    -Description "LeadEnricher - BANT + persona + email guess (P22.H), tous les jours 07:15"

# -----------------------------------------------------------------------------
# IntentSignalsBot - quotidien 08:00
# -----------------------------------------------------------------------------
$intentTrigger = New-ScheduledTaskTrigger -Daily -At "08:00"
Register-SalesTask `
    -TaskName "argos-ops-intent-signals" `
    -ScriptRelPath "scripts\run_intent_signals.py" `
    -Trigger $intentTrigger `
    -Description "IntentSignalsBot - signaux achat publics (P22.H), tous les jours 08:00"

# -----------------------------------------------------------------------------
# OutboundBot - quotidien 09:00 (apres enrich + signals)
# -----------------------------------------------------------------------------
$outboundTrigger = New-ScheduledTaskTrigger -Daily -At "09:00"
Register-SalesTask `
    -TaskName "argos-ops-outbound" `
    -ScriptRelPath "scripts\run_outbound_bot.py" `
    -Trigger $outboundTrigger `
    -Description "OutboundBot - scaffold sequences shadow (P13.A/P22.H), tous les jours 09:00"

# -----------------------------------------------------------------------------
# DealRiskScorer - hebdo lundi 08:30
# -----------------------------------------------------------------------------
$dealTrigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday -At "08:30"
Register-SalesTask `
    -TaskName "argos-ops-deal-scoring" `
    -ScriptRelPath "scripts\run_deal_risk_scorer.py" `
    -Trigger $dealTrigger `
    -Description "DealRiskScorer - score pipe + flag stalled (P22.H), lundi 08:30"

# -----------------------------------------------------------------------------
# Recap
# -----------------------------------------------------------------------------
if (-not $DryRun) {
    Write-Host "=== Recap ===" -ForegroundColor Cyan
    Get-ScheduledTask `
        -TaskName "argos-ops-prospect-mining", "argos-ops-lead-enrich", `
                  "argos-ops-intent-signals", "argos-ops-outbound", `
                  "argos-ops-deal-scoring" `
        | Get-ScheduledTaskInfo `
        | Format-Table TaskName, LastRunTime, LastTaskResult, NextRunTime
}

Write-Host ""
Write-Host "[i] Pour tester immediatement (Docker requis) :"
Write-Host "    Start-ScheduledTask -TaskName 'argos-ops-prospect-mining'"
Write-Host "    Start-ScheduledTask -TaskName 'argos-ops-lead-enrich'"
Write-Host "    Start-ScheduledTask -TaskName 'argos-ops-intent-signals'"
Write-Host "    Start-ScheduledTask -TaskName 'argos-ops-outbound'"
Write-Host "    Start-ScheduledTask -TaskName 'argos-ops-deal-scoring'"
Write-Host ""
Write-Host "[i] Bots reactifs (slash only, pas dans Task Scheduler) :"
Write-Host "    /book-meeting / /draft-demo-followup / /draft-proposal / /draft-contract"
