<#
.SYNOPSIS
  Idempotent setup des taches Task Scheduler Windows pour la famille
  Finance & Tresorerie (P22.F) : 7 bots.

.DESCRIPTION
  Sept bots planifies :

  - argos-ops-finance-sync         - tous les jours 06:00     - sync Stripe + dunning
  - argos-ops-invoice-forecast     - lundi 07:00 (hebdo)      - cash flow 30/60/90j
  - argos-ops-reconcile            - lundi 07:15 (hebdo)      - Stripe payouts vs Qonto
  - argos-ops-burn-rate            - lundi 07:30 (hebdo)      - runway < 9 mois
  - argos-ops-vendor-contracts     - lundi 07:45 (hebdo)      - tacite reconduction
  - argos-ops-expense-audit        - 5 du mois 07:00 (mensuel) - anomalies Qonto
  - argos-ops-tax-prep             - 15 du mois 07:00 (mensuel) - TVA CA3 + IS

  Idempotent - relancer ecrase les taches existantes.

.EXAMPLE
  PS> .\scripts\setup_finance_tasks.ps1
  Cree ou met a jour les 7 taches.

  PS> .\scripts\setup_finance_tasks.ps1 -DryRun
  Affiche ce qui serait fait, sans toucher au Task Scheduler.

.NOTES
  Lancer en PowerShell avec autorisations admin. Docker container
  argos-postgres-local doit tourner pour que les runs aboutissent.
  D-017 - bots locaux sur l'ordi du fondateur.
#>

[CmdletBinding()]
param(
    [switch] $DryRun
)

$ErrorActionPreference = "Stop"

$RepoRoot = "C:\Users\pauzzle\Desktop\argos-ops"
# Path absolu requis : Task Scheduler n'herite pas du PATH utilisateur.
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

function Register-FinanceTask {
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

# Helper pour les taches mensuelles (jour fixe du mois) via XML.
function Register-MonthlyTask {
    param(
        [Parameter(Mandatory)] [string] $TaskName,
        [Parameter(Mandatory)] [string] $ScriptRelPath,
        [Parameter(Mandatory)] [int] $DayOfMonth,
        [Parameter(Mandatory)] [string] $TimeOfDay,  # ex "07:00"
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

    $dayPadded = $DayOfMonth.ToString("D2")
    $startBoundary = "2026-01-${dayPadded}T${TimeOfDay}:00"
    $xml = @"
<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.4" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Description>$Description</Description>
  </RegistrationInfo>
  <Triggers>
    <CalendarTrigger>
      <StartBoundary>$startBoundary</StartBoundary>
      <Enabled>true</Enabled>
      <ScheduleByMonth>
        <DaysOfMonth><Day>$DayOfMonth</Day></DaysOfMonth>
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
      <Arguments>run python $ScriptRelPath</Arguments>
      <WorkingDirectory>$RepoRoot</WorkingDirectory>
    </Exec>
  </Actions>
</Task>
"@

    if ($DryRun) {
        Write-Host "[DRY-RUN] OK." -ForegroundColor Green
        Write-Host ""
        return
    }

    $existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if ($existing) {
        Write-Host "[INFO] Tache existante detectee - sera remplacee." -ForegroundColor Yellow
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    }
    Register-ScheduledTask -TaskName $TaskName -Xml $xml | Out-Null
    Write-Host "[OK] Tache '$TaskName' enregistree." -ForegroundColor Green
    Write-Host ""
}

# -----------------------------------------------------------------------------
# FinanceBot - quotidien 06:00
# -----------------------------------------------------------------------------
$dailyTrigger = New-ScheduledTaskTrigger -Daily -At "06:00"
Register-FinanceTask `
    -TaskName "argos-ops-finance-sync" `
    -ScriptRelPath "scripts\run_finance_bot.py" `
    -Trigger $dailyTrigger `
    -Description "FinanceBot - sync Stripe + dunning (P7), tous les jours 06:00"

# -----------------------------------------------------------------------------
# InvoicePredictor - hebdo lundi 07:00
# -----------------------------------------------------------------------------
$invoiceTrigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday -At "07:00"
Register-FinanceTask `
    -TaskName "argos-ops-invoice-forecast" `
    -ScriptRelPath "scripts\run_invoice_predictor.py" `
    -Trigger $invoiceTrigger `
    -Description "InvoicePredictor - forecast cash flow 30/60/90j (P22.F), lundi 07:00"

# -----------------------------------------------------------------------------
# ReconcileBot - hebdo lundi 07:15
# -----------------------------------------------------------------------------
$reconcileTrigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday -At "07:15"
Register-FinanceTask `
    -TaskName "argos-ops-reconcile" `
    -ScriptRelPath "scripts\run_reconcile_bot.py" `
    -Trigger $reconcileTrigger `
    -Description "ReconcileBot - Stripe payouts vs Qonto (P22.F), lundi 07:15"

# -----------------------------------------------------------------------------
# BurnRateMonitor - hebdo lundi 07:30
# -----------------------------------------------------------------------------
$burnTrigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday -At "07:30"
Register-FinanceTask `
    -TaskName "argos-ops-burn-rate" `
    -ScriptRelPath "scripts\run_burn_rate_monitor.py" `
    -Trigger $burnTrigger `
    -Description "BurnRateMonitor - alerte runway < 9m (P22.F), lundi 07:30"

# -----------------------------------------------------------------------------
# VendorContractWatcher - hebdo lundi 07:45
# -----------------------------------------------------------------------------
$vendorTrigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday -At "07:45"
Register-FinanceTask `
    -TaskName "argos-ops-vendor-contracts" `
    -ScriptRelPath "scripts\run_vendor_contract_watcher.py" `
    -Trigger $vendorTrigger `
    -Description "VendorContractWatcher - tacite reconduction (P22.F), lundi 07:45"

# -----------------------------------------------------------------------------
# ExpenseAuditor - mensuel le 5 a 07:00 (apres agregation Qonto)
# -----------------------------------------------------------------------------
Register-MonthlyTask `
    -TaskName "argos-ops-expense-audit" `
    -ScriptRelPath "scripts\run_expense_auditor.py" `
    -DayOfMonth 5 `
    -TimeOfDay "07:00" `
    -Description "ExpenseAuditor - anomalies CSV Qonto (P22.F), 5 du mois 07:00"

# -----------------------------------------------------------------------------
# TaxBot - mensuel le 15 a 07:00 (avant deadline TVA CA3 du 19)
# -----------------------------------------------------------------------------
Register-MonthlyTask `
    -TaskName "argos-ops-tax-prep" `
    -ScriptRelPath "scripts\run_tax_bot.py" `
    -DayOfMonth 15 `
    -TimeOfDay "07:00" `
    -Description "TaxBot - TVA CA3 + IS previsionnel (P22.F), 15 du mois 07:00"

# -----------------------------------------------------------------------------
# Recap
# -----------------------------------------------------------------------------
if (-not $DryRun) {
    Write-Host "=== Recap ===" -ForegroundColor Cyan
    Get-ScheduledTask `
        -TaskName "argos-ops-finance-sync", "argos-ops-invoice-forecast", "argos-ops-reconcile", `
                  "argos-ops-burn-rate", "argos-ops-vendor-contracts", `
                  "argos-ops-expense-audit", "argos-ops-tax-prep" `
        | Get-ScheduledTaskInfo `
        | Format-Table TaskName, LastRunTime, LastTaskResult, NextRunTime
}

Write-Host ""
Write-Host "[i] Pour tester immediatement (Docker requis) :"
Write-Host "    Start-ScheduledTask -TaskName 'argos-ops-finance-sync'"
Write-Host "    Start-ScheduledTask -TaskName 'argos-ops-invoice-forecast'"
Write-Host "    Start-ScheduledTask -TaskName 'argos-ops-reconcile'"
Write-Host "    Start-ScheduledTask -TaskName 'argos-ops-burn-rate'"
Write-Host "    Start-ScheduledTask -TaskName 'argos-ops-vendor-contracts'"
Write-Host "    Start-ScheduledTask -TaskName 'argos-ops-expense-audit'"
Write-Host "    Start-ScheduledTask -TaskName 'argos-ops-tax-prep'"
