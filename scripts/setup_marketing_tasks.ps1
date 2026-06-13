<#
.SYNOPSIS
  Idempotent setup des taches Task Scheduler Windows pour la famille
  Marketing & Growth (P22.I) : 10 bots cron + 2 bots reactifs.

.DESCRIPTION
  Dix bots planifies :

  Cadence haute (multi-fois par jour) :
  - argos-ops-content-publish    - */2 heures 08-20  - publie drafts validés

  Cadence quotidienne :
  - argos-ops-trend-spot         - quotidien 07:30   - top sujets cyber
  - argos-ops-ad-campaign        - quotidien 09:00   - apply ads recos (shadow)
  - argos-ops-testimonial        - quotidien 15:00   - drafte demandes verbatim

  Cadence hebdomadaire :
  - argos-ops-social-analytics   - lundi 09:00       - engagement 7j
  - argos-ops-keyword-radar      - lundi 09:15       - SERP movements
  - argos-ops-landing-optim      - mardi 09:00       - A/B hypotheses

  Cadence mensuelle :
  - argos-ops-newsletter         - 1er du mois 10:00 - drafte newsletter

  Reactifs (slash only, pas dans Task Scheduler) :
  - SEOBot              : /generate-seo-brief (humain-in-the-loop)

  (WebinarPromoter / BacklinkOutreach / CaseStudyDrafter retires par D-030.)

  Idempotent - relancer ecrase les taches existantes.

.EXAMPLE
  PS> .\scripts\setup_marketing_tasks.ps1
  PS> .\scripts\setup_marketing_tasks.ps1 -DryRun

.NOTES
  Lancer en PowerShell admin. Docker container argos-postgres-local UP.
  ContentBot/AdBot restent shadow tant que CONTENT_LIVE_MODE/ADS_LIVE_MODE
  ne sont pas explicitement activés dans .env.local.
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

function Register-MarketingTask {
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
# ContentBot - toutes les 2h entre 08:00 et 20:00
# -----------------------------------------------------------------------------
# 7 tirs : 08, 10, 12, 14, 16, 18, 20. Trigger Once + Repetition.
$contentStart = (Get-Date).Date.AddHours(8)
$contentTrigger = New-ScheduledTaskTrigger -Once -At $contentStart `
    -RepetitionInterval (New-TimeSpan -Hours 2) `
    -RepetitionDuration (New-TimeSpan -Hours 12)
Register-MarketingTask `
    -TaskName "argos-ops-content-publish" `
    -ScriptRelPath "scripts\run_content_bot.py" `
    -Trigger $contentTrigger `
    -Description "ContentBot - publie drafts validés LinkedIn/Mastodon (P22.I), toutes les 2h 08-20"

# -----------------------------------------------------------------------------
# TrendSpotter - quotidien 07:30
# -----------------------------------------------------------------------------
$trendTrigger = New-ScheduledTaskTrigger -Daily -At "07:30"
Register-MarketingTask `
    -TaskName "argos-ops-trend-spot" `
    -ScriptRelPath "scripts\run_trend_spotter.py" `
    -Trigger $trendTrigger `
    -Description "TrendSpotter - top sujets cyber (P22.I), tous les jours 07:30"

# -----------------------------------------------------------------------------
# AdBot - quotidien 09:00
# -----------------------------------------------------------------------------
$adTrigger = New-ScheduledTaskTrigger -Daily -At "09:00"
Register-MarketingTask `
    -TaskName "argos-ops-ad-campaign" `
    -ScriptRelPath "scripts\run_ad_bot_live.py" `
    -Trigger $adTrigger `
    -Description "AdBot - apply ads recos shadow (P22.I), tous les jours 09:00"

# -----------------------------------------------------------------------------
# TestimonialHunter - quotidien 15:00
# -----------------------------------------------------------------------------
$testimonialTrigger = New-ScheduledTaskTrigger -Daily -At "15:00"
Register-MarketingTask `
    -TaskName "argos-ops-testimonial" `
    -ScriptRelPath "scripts\run_testimonial_hunter.py" `
    -Trigger $testimonialTrigger `
    -Description "TestimonialHunter - drafte demandes verbatim (P22.I), tous les jours 15:00"

# -----------------------------------------------------------------------------
# SocialAnalytics - hebdo lundi 09:00
# -----------------------------------------------------------------------------
$socialTrigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday -At "09:00"
Register-MarketingTask `
    -TaskName "argos-ops-social-analytics" `
    -ScriptRelPath "scripts\run_social_analytics.py" `
    -Trigger $socialTrigger `
    -Description "SocialAnalytics - engagement 7j par canal (P22.I), lundi 09:00"

# -----------------------------------------------------------------------------
# KeywordRadar - hebdo lundi 09:15
# -----------------------------------------------------------------------------
$keywordTrigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday -At "09:15"
Register-MarketingTask `
    -TaskName "argos-ops-keyword-radar" `
    -ScriptRelPath "scripts\run_keyword_radar.py" `
    -Trigger $keywordTrigger `
    -Description "KeywordRadar - SERP movements (P22.I), lundi 09:15"

# -----------------------------------------------------------------------------
# LandingOptimizer - hebdo mardi 09:00
# -----------------------------------------------------------------------------
$landingTrigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Tuesday -At "09:00"
Register-MarketingTask `
    -TaskName "argos-ops-landing-optim" `
    -ScriptRelPath "scripts\run_landing_optimizer.py" `
    -Trigger $landingTrigger `
    -Description "LandingOptimizer - A/B hypotheses (P22.I), mardi 09:00"

# -----------------------------------------------------------------------------
# NewsletterBot - mensuel le 1er a 10:00 (via XML CalendarTrigger)
# -----------------------------------------------------------------------------
$newsletterTaskName = "argos-ops-newsletter"
$newsletterScriptRel = "scripts\run_newsletter_bot.py"
$newsletterAbsPath = Join-Path $RepoRoot $newsletterScriptRel

Write-Host "=== $newsletterTaskName ===" -ForegroundColor Cyan
Write-Host "  Script   : $newsletterScriptRel"
Write-Host "  Trigger  : NewsletterBot mensuel, 1er du mois 10:00"
Write-Host "  DryRun   : $($DryRun.IsPresent)"

if (-not (Test-Path $newsletterAbsPath)) {
    Write-Error "Script introuvable : $newsletterAbsPath"
    exit 1
}

$newsletterXml = @"
<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.4" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Description>NewsletterBot - drafte newsletter mensuelle (P22.I), 1er du mois 10:00</Description>
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
      <Arguments>run python $newsletterScriptRel</Arguments>
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
    $existing = Get-ScheduledTask -TaskName $newsletterTaskName -ErrorAction SilentlyContinue
    if ($existing) {
        Write-Host "[INFO] Tache existante detectee - sera remplacee." -ForegroundColor Yellow
        Unregister-ScheduledTask -TaskName $newsletterTaskName -Confirm:$false
    }
    Register-ScheduledTask -TaskName $newsletterTaskName -Xml $newsletterXml | Out-Null
    Write-Host "[OK] Tache '$newsletterTaskName' enregistree." -ForegroundColor Green
    Write-Host ""
}

# -----------------------------------------------------------------------------
# Recap
# -----------------------------------------------------------------------------
if (-not $DryRun) {
    Write-Host "=== Recap ===" -ForegroundColor Cyan
    Get-ScheduledTask `
        -TaskName "argos-ops-content-publish", "argos-ops-trend-spot", `
                  "argos-ops-ad-campaign", "argos-ops-testimonial", `
                  "argos-ops-social-analytics", "argos-ops-keyword-radar", `
                  "argos-ops-landing-optim", "argos-ops-newsletter" `
        | Get-ScheduledTaskInfo `
        | Format-Table TaskName, LastRunTime, LastTaskResult, NextRunTime
}

Write-Host ""
Write-Host "[i] Pour tester immediatement (Docker requis) :"
Write-Host "    Start-ScheduledTask -TaskName 'argos-ops-trend-spot'"
Write-Host "    Start-ScheduledTask -TaskName 'argos-ops-social-analytics'"
Write-Host ""
Write-Host "[i] Bots reactifs (slash only) :"
Write-Host "    /generate-seo-brief   (SEOBot)"
