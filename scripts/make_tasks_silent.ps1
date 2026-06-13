<#
.SYNOPSIS
  Passe toutes les taches planifiees Argos Ops (argos-ops-*) en execution
  SILENCIEUSE — plus aucune fenetre PowerShell/console qui s'ouvre au
  declenchement du cron.

.DESCRIPTION
  Par defaut, Register-ScheduledTask cree des taches avec un principal
  "interactif" : le process uv/python tourne dans la session visible de
  l'utilisateur, donc Windows affiche une fenetre console a chaque tir
  (toutes les 5 min pour argos-ops-uptime, par ex.).

  Ce script bascule le principal de chaque tache "argos-ops-*" en
  LogonType S4U (= "Executer meme si l'utilisateur n'est pas connecte",
  case "Ne pas enregistrer le mot de passe"). Une tache S4U s'execute
  dans la session 0 (non-interactive) : le job tourne en arriere-plan,
  AUCUNE fenetre n'apparait, et aucun mot de passe n'est stocke.

  Tous les bots Argos Ops sont des scripts Python headless (DB + Discord
  + HTTP sortant) qui n'ont jamais besoin d'un terminal — S4U est donc
  sans risque fonctionnel ici.

  Idempotent : relancer ne touche pas une tache deja en S4U.

.PARAMETER DryRun
  Affiche le plan (quelle tache passerait de quel mode a quel mode) sans
  rien modifier.

.PARAMETER Revert
  Repasse les taches en mode Interactive (la fenetre reapparait). Utile
  pour debugger une tache visuellement.

.EXAMPLE
  PS> .\scripts\make_tasks_silent.ps1
  Passe toutes les taches argos-ops-* en silencieux.

  PS> .\scripts\make_tasks_silent.ps1 -DryRun
  Montre ce qui changerait, sans rien appliquer.

  PS> .\scripts\make_tasks_silent.ps1 -Revert
  Repasse tout en interactif (fenetre visible).

.NOTES
  Lancer en PowerShell ADMIN (clic droit -> Executer en tant
  qu'administrateur). Le passage en S4U exige le privilege "Log on as a
  batch job", accorde automatiquement par l'OS mais seulement en
  contexte eleve.

  D-017 — taches locales sur l'ordi du fondateur, pas sur le serveur.
#>

[CmdletBinding()]
param(
    [switch] $DryRun,
    [switch] $Revert
)

$ErrorActionPreference = "Stop"

$Prefix = "argos-ops-*"
$UserId = "$env:USERDOMAIN\$env:USERNAME"

if ($Revert) {
    $targetLogon = "Interactive"
    $principal = New-ScheduledTaskPrincipal -UserId $UserId -LogonType Interactive -RunLevel Limited
    $modeLabel = "INTERACTIVE (fenetre visible)"
}
else {
    $targetLogon = "S4U"
    $principal = New-ScheduledTaskPrincipal -UserId $UserId -LogonType S4U -RunLevel Limited
    $modeLabel = "S4U / silencieux (aucune fenetre)"
}

$tasks = @(Get-ScheduledTask -TaskName $Prefix -ErrorAction SilentlyContinue)
if (-not $tasks -or $tasks.Count -eq 0) {
    Write-Warning "Aucune tache '$Prefix' trouvee. Lance d'abord les scripts setup_*_tasks.ps1."
    exit 1
}

Write-Host "=== Silence des taches Argos Ops ===" -ForegroundColor Cyan
Write-Host "  Compte  : $UserId"
Write-Host "  Cible   : $modeLabel"
Write-Host "  Taches  : $($tasks.Count)"
Write-Host "  DryRun  : $($DryRun.IsPresent)"
Write-Host ""

$ok = 0; $skip = 0; $err = 0
foreach ($t in $tasks) {
    $name = $t.TaskName
    $current = [string] $t.Principal.LogonType

    if ($current -eq $targetLogon) {
        Write-Host "[$name] deja en $current - skip" -ForegroundColor DarkGray
        $skip++
        continue
    }

    Write-Host "[$name] $current -> $targetLogon" -ForegroundColor Yellow
    if ($DryRun) { continue }

    try {
        Set-ScheduledTask -TaskName $name -Principal $principal | Out-Null
        Write-Host "  [OK]" -ForegroundColor Green
        $ok++
    }
    catch {
        Write-Host "  [ERREUR] $($_.Exception.Message)" -ForegroundColor Red
        $err++
    }
}

Write-Host ""
Write-Host "Termine. OK=$ok  skip=$skip  erreurs=$err" -ForegroundColor Cyan
if ($err -gt 0) {
    Write-Host "[!] Des erreurs -> relance ce script en PowerShell ADMIN." -ForegroundColor Red
}
Write-Host ""
Write-Host "[i] Verifier le mode de chaque tache :" -ForegroundColor DarkGray
Write-Host "    Get-ScheduledTask -TaskName 'argos-ops-*' | Select-Object TaskName, @{N='Logon';E={`$_.Principal.LogonType}}"
