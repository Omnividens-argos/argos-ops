---
description: Lance DependencyAuditor — scan deps via uv export + check CVE OSV.dev, alerte HIGH/CRITICAL (silence si OK)
---

# /run-dep-audit

Slash command Claude Code invoquée manuellement ou par Task Scheduler
(`argos-ops-dep-audit`, hebdomadaire) **sur l'ordi du fondateur** (D-017).

## Procédure

1. Lance `uv run python scripts/run_dependency_auditor.py` (foreground, ~10-30 sec selon le nombre de deps + API OSV).
2. Lis la sortie loguru et l'exit code.
3. **Si exit 0 et `output_summary` commence par `silence (vert)`** : aucune vuln MEDIUM+ sur les deps actuelles.
4. **Si exit 0 et `output_summary` commence par `alert pushed`** : embed jaune (MEDIUM) ou rouge (HIGH/CRITICAL). Lis le summary (ex : `1 CRITICAL · 2 HIGH · 3 MEDIUM (sur 178 deps)`). Propose au founder de :
   - HIGH/CRITICAL : `uv lock --upgrade-package <name>` puis `uv sync`, tester, commit `chore(deps): bump X for CVE-YYYY-XXXX`
   - MEDIUM : peut attendre une window de maintenance
5. **Si exit 0 et `output_summary` commence par `alerte non envoyée`** : webhook absent.
6. **Si exit 1** : erreur subprocess `uv export` ou OSV.dev injoignable.

## Notes

- API utilisée : `https://api.osv.dev/v1/querybatch` (gratuite, publique, aucune clé requise) + `/v1/vulns/{id}` pour les détails.
- Mapping severity : CVSS 9.0+ → CRITICAL, 7.0+ → HIGH, 4.0+ → MEDIUM, 0.1+ → LOW.
- LOW vulnerabilities sont masquées dans l'embed (bruit de fond, à check manuellement si curieux).
- Quand on bump un paquet pour fix une CVE : mentionner le ID CVE dans le commit message pour traçabilité.
