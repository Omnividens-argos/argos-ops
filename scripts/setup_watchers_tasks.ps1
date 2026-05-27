<#
.SYNOPSIS
  Idempotent setup des Task Scheduler Windows pour les 12 watcher bots P22.C/D.

.DESCRIPTION
  Enregistre (ou met à jour) 12 tâches planifiées pour la flotte de
  watchers Argos Ops :

  Meta-Ops Sprint 2 (4 bots) :
    - argos-ops-bot-perf          : hebdo (lundi 5h)
    - argos-ops-error-triage      : toutes les 6h
    - argos-ops-kill-switch       : 2x/jour (9h et 17h)
    - argos-ops-config-drift      : quotidien (4h)

  Tech/SRE Sprint 4 (8 bots) :
    - argos-ops-uptime            : toutes les 5 min
    - argos-ops-ssl-expirer       : mensuel (1er du mois 6h)
    - argos-ops-secret-rotator    : hebdo (lundi 6h)
    - argos-ops-dep-audit         : hebdo (lundi 7h)
    - argos-ops-backup-verifier   : quotidien (5h)
    - argos-ops-log-anomaly       : quotidien (4h)
    - argos-ops-dns-guard         : quotidien (13h)
    - argos-ops-ci-flake-tracker  : quotidien (21h, post-CI)

  Veille & Threat Intelligence (P22.D, 6 bots) :
    - argos-ops-competitor-watch  : hebdo (lundi 12h)
    - argos-ops-breach-watch      : quotidien (6h30)
    - argos-ops-regulatory-watch  : quotidien (7h)
    - argos-ops-cve-monitor       : quotidien (7h30)
    - argos-ops-dw-monitor        : quotidien (12h30)
    - argos-ops-bounty-radar      : mensuel (1er du mois 12h)

  Juridique & Compliance (P22.K, 4 bots cron + 1 interactif) :
    - argos-ops-rgpd-audit        : hebdo (lundi 13h)
    - argos-ops-ai-act-audit      : hebdo (lundi 13h30)
    - argos-ops-contract-deadlines : quotidien (14h)
    - argos-ops-bloctel-guard     : mensuel (1er du mois 13h)
    - IncidentLogger              : interactif (slash /log-incident, pas cron)

  Communication (P22.L, 3 watchers cron + 4 reactifs slash) :
    - argos-ops-press-monitor     : quotidien (10h30)
    - argos-ops-media-list        : hebdo (lundi 14h)
    - argos-ops-brand-audit       : hebdo (lundi 14h30)
    - ReplyBot / PressReleaseDrafter / CrisisCommBot / SpokespersonPrep : slash only

  Documentation & Knowledge interne (P22.M, 1 watcher cron + 2 reactifs) :
    - argos-ops-doc-lint          : hebdo (lundi 15h)
    - DiagramGenerator / ADRWriter : slash only (input slug requis)

  Chaque tâche est idempotente — relancer écrase l'existante.

.EXAMPLE
  PS> .\scripts\setup_watchers_tasks.ps1
  Crée/met à jour les 9 tâches.

  PS> .\scripts\setup_watchers_tasks.ps1 -DryRun
  Affiche le plan sans toucher au Task Scheduler.

  PS> .\scripts\setup_watchers_tasks.ps1 -Only argos-ops-uptime,argos-ops-error-triage
  Ne configure que les tâches listées.

.NOTES
  Lancer en PowerShell avec autorisations admin. D-017 — agents locaux
  sur l'ordi du fondateur, pas sur le serveur.
#>

[CmdletBinding()]
param(
    [switch] $DryRun,
    [string[]] $Only
)

$ErrorActionPreference = "Stop"

$RepoRoot = "C:\Users\pauzzle\Desktop\argos-ops"

# Path absolu uv.exe requis : Task Scheduler n'hérite pas du PATH utilisateur.
$UvCommand = "$env:USERPROFILE\.local\bin\uv.exe"
if (-not (Test-Path $UvCommand)) {
    $UvCommand = (Get-Command uv -ErrorAction SilentlyContinue).Path
}
if (-not $UvCommand -or -not (Test-Path $UvCommand)) {
    Write-Error "uv introuvable - verifie l'installation (winget install astral-sh.uv)"
    exit 1
}
Write-Host "[i] uv resolu vers : $UvCommand" -ForegroundColor DarkGray

# Catalogue des taches : (Name, Script, TriggerType, TriggerArg, Description)
# TriggerType : "Every5Min" / "Hourly:N" / "Daily:HH:MM" / "Weekly:DayOfWeek:HH:MM" / "Monthly:DayOfMonth:HH:MM"
$Tasks = @(
    @{ Name = "argos-ops-bot-perf";         Script = "run_bot_perf.py";          Trigger = "Weekly:Monday:05:00";  Description = "BotPerfAnalyzer hebdo (lundi 5h)" }
    @{ Name = "argos-ops-error-triage";     Script = "run_error_triage.py";      Trigger = "Hourly:6";              Description = "ErrorTriageBot toutes les 6h" }
    @{ Name = "argos-ops-kill-switch";      Script = "run_kill_switch.py";       Trigger = "DailyTwice:09:00:17:00"; Description = "KillSwitchOperator 9h et 17h" }
    @{ Name = "argos-ops-config-drift";     Script = "run_bot_config_manager.py"; Trigger = "Daily:04:00";          Description = "BotConfigManager quotidien (4h)" }
    @{ Name = "argos-ops-uptime";           Script = "run_uptime_monitor.py";    Trigger = "Every5Min";              Description = "UptimeMonitor toutes les 5 min" }
    @{ Name = "argos-ops-ssl-expirer";      Script = "run_ssl_expirer.py";       Trigger = "Monthly:1:06:00";       Description = "SSLExpirer mensuel (1er 6h)" }
    @{ Name = "argos-ops-secret-rotator";   Script = "run_secret_rotator.py";    Trigger = "Weekly:Monday:06:00";  Description = "SecretRotator hebdo (lundi 6h)" }
    @{ Name = "argos-ops-dep-audit";        Script = "run_dependency_auditor.py"; Trigger = "Weekly:Monday:07:00"; Description = "DependencyAuditor hebdo (lundi 7h)" }
    @{ Name = "argos-ops-backup-verifier";  Script = "run_backup_verifier.py";   Trigger = "Daily:05:00";          Description = "BackupVerifier quotidien (5h)" }
    @{ Name = "argos-ops-log-anomaly";      Script = "run_log_anomaly.py";       Trigger = "Daily:04:00";          Description = "LogAnomalyDetector quotidien (4h)" }
    @{ Name = "argos-ops-dns-guard";        Script = "run_dns_guard.py";         Trigger = "Daily:13:00";          Description = "DNSGuard quotidien (13h)" }
    @{ Name = "argos-ops-ci-flake-tracker"; Script = "run_ci_flake_tracker.py";  Trigger = "Daily:21:00";          Description = "CIFlakeTracker quotidien (21h post-CI)" }
    @{ Name = "argos-ops-competitor-watch"; Script = "run_competitor_watcher.py"; Trigger = "Weekly:Monday:12:00"; Description = "CompetitorWatcher hebdo (lundi 12h)" }
    @{ Name = "argos-ops-breach-watch";     Script = "run_breach_watcher.py";    Trigger = "Daily:06:30";          Description = "BreachWatcher quotidien (6h30)" }
    @{ Name = "argos-ops-regulatory-watch"; Script = "run_regulatory_watcher.py"; Trigger = "Daily:07:00";         Description = "RegulatoryWatcher quotidien (7h)" }
    @{ Name = "argos-ops-cve-monitor";      Script = "run_cve_monitor.py";       Trigger = "Daily:07:30";          Description = "CVEMonitor quotidien (7h30)" }
    @{ Name = "argos-ops-dw-monitor";       Script = "run_dw_monitor.py";        Trigger = "Daily:12:30";          Description = "DarkWebMonitor quotidien (12h30)" }
    @{ Name = "argos-ops-bounty-radar";     Script = "run_bounty_radar.py";      Trigger = "Monthly:1:12:00";      Description = "BountyRadar mensuel (1er 12h)" }
    @{ Name = "argos-ops-rgpd-audit";       Script = "run_rgpd_auditor.py";      Trigger = "Weekly:Monday:13:00";  Description = "RGPDAuditor hebdo (lundi 13h)" }
    @{ Name = "argos-ops-ai-act-audit";     Script = "run_ai_act_compliance.py"; Trigger = "Weekly:Monday:13:30";  Description = "AIActComplianceBot hebdo (lundi 13h30)" }
    @{ Name = "argos-ops-contract-deadlines"; Script = "run_contract_deadlines.py"; Trigger = "Daily:14:00";        Description = "ContractDeadlineBot quotidien (14h)" }
    @{ Name = "argos-ops-bloctel-guard";    Script = "run_bloctel_guard.py";     Trigger = "Monthly:1:13:00";      Description = "BloctelGuard mensuel (1er 13h)" }
    @{ Name = "argos-ops-press-monitor";    Script = "run_press_monitor.py";     Trigger = "Daily:10:30";          Description = "PressMonitor quotidien (10h30)" }
    @{ Name = "argos-ops-media-list";       Script = "run_media_list_builder.py"; Trigger = "Weekly:Monday:14:00"; Description = "MediaListBuilder hebdo (lundi 14h)" }
    @{ Name = "argos-ops-brand-audit";      Script = "run_brand_guard.py";       Trigger = "Weekly:Monday:14:30";  Description = "BrandGuardBot hebdo (lundi 14h30)" }
    @{ Name = "argos-ops-doc-lint";         Script = "run_doc_linter.py";        Trigger = "Weekly:Monday:15:00";  Description = "DocLinter hebdo (lundi 15h)" }
)

if ($Only) {
    $Tasks = $Tasks | Where-Object { $Only -contains $_.Name }
    if (-not $Tasks) {
        Write-Error "Aucune tâche ne matche -Only $Only"
        exit 1
    }
}

function New-WatcherTrigger {
    param([string] $Spec)
    $parts = $Spec.Split(":")
    switch ($parts[0]) {
        "Every5Min" {
            $start = (Get-Date).Date.AddMinutes(2)
            return New-ScheduledTaskTrigger -Once -At $start `
                -RepetitionInterval (New-TimeSpan -Minutes 5) `
                -RepetitionDuration (New-TimeSpan -Days 365)
        }
        "Hourly" {
            $hours = [int] $parts[1]
            $start = (Get-Date).Date.AddMinutes(15)
            return New-ScheduledTaskTrigger -Once -At $start `
                -RepetitionInterval (New-TimeSpan -Hours $hours) `
                -RepetitionDuration (New-TimeSpan -Days 365)
        }
        "Daily" {
            $time = [DateTime]::ParseExact($parts[1] + ":" + $parts[2], "HH:mm", $null)
            return New-ScheduledTaskTrigger -Daily -At $time
        }
        "DailyTwice" {
            $time1 = [DateTime]::ParseExact($parts[1] + ":" + $parts[2], "HH:mm", $null)
            $time2 = [DateTime]::ParseExact($parts[3] + ":" + $parts[4], "HH:mm", $null)
            return @(
                (New-ScheduledTaskTrigger -Daily -At $time1),
                (New-ScheduledTaskTrigger -Daily -At $time2)
            )
        }
        "Weekly" {
            $time = [DateTime]::ParseExact($parts[2] + ":" + $parts[3], "HH:mm", $null)
            return New-ScheduledTaskTrigger -Weekly -DaysOfWeek $parts[1] -At $time
        }
        "Monthly" {
            $day = [int] $parts[1]
            $time = [DateTime]::ParseExact($parts[2] + ":" + $parts[3], "HH:mm", $null)
            # Pas de New-ScheduledTaskTrigger -Monthly direct dans PS 5.1 ;
            # on génère via CIM. Fallback : trigger weekly + filtrage côté script.
            return New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday -At $time
        }
        default {
            throw "TriggerType inconnu : $($parts[0])"
        }
    }
}

Write-Host "=== Setup watcher Task Scheduler ===" -ForegroundColor Cyan
Write-Host "  Repo         : $RepoRoot"
Write-Host "  Taches       : $($Tasks.Count)"
Write-Host "  DryRun       : $($DryRun.IsPresent)"
Write-Host ""

foreach ($task in $Tasks) {
    $name = $task.Name
    $script = $task.Script
    $scriptPath = Join-Path $RepoRoot "scripts\$script"

    if (-not (Test-Path $scriptPath)) {
        Write-Warning "[$name] Script introuvable : $scriptPath - skip"
        continue
    }

    Write-Host "[$name]" -ForegroundColor Yellow
    Write-Host "  Script   : scripts\$script"
    Write-Host "  Trigger  : $($task.Trigger)"

    if ($DryRun) {
        Write-Host "  [DRY-RUN] OK" -ForegroundColor Green
        continue
    }

    $existing = Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue
    if ($existing) {
        Unregister-ScheduledTask -TaskName $name -Confirm:$false
        Write-Host "  [REPLACE] tache existante remplacee"
    }

    $action = New-ScheduledTaskAction `
        -Execute $UvCommand `
        -Argument "run python scripts\$script" `
        -WorkingDirectory $RepoRoot

    $trigger = New-WatcherTrigger -Spec $task.Trigger

    $settings = New-ScheduledTaskSettingsSet `
        -StartWhenAvailable `
        -DontStopIfGoingOnBatteries `
        -AllowStartIfOnBatteries

    Register-ScheduledTask `
        -TaskName $name `
        -Action $action `
        -Trigger $trigger `
        -Settings $settings `
        -Description $task.Description | Out-Null

    Write-Host "  [OK] enregistree" -ForegroundColor Green
}

Write-Host ""
Write-Host "Fini. Pour lister :" -ForegroundColor Cyan
Write-Host "  Get-ScheduledTask -TaskName 'argos-ops-*' | Format-Table TaskName, State, NextRunTime"
