---
description: Lance LeadEnricher — batch d'enrichissement BANT/persona/email de chaque lead inbox CSV. Idempotent, écrit data/outbound/enriched/<slug>.md.
---

# /run-lead-enrich

Slash command Claude Code invoquée manuellement ou par Task Scheduler (`argos-ops-lead-enrich`, cadence quotidienne 7h15 Paris, juste après ProspectMiner) **sur l'ordi du fondateur** (D-017).

## Procédure

1. Lance `uv run python scripts/run_lead_enricher.py` (foreground, ~2-5 sec selon volume CSV).
2. Lis la sortie loguru et l'exit code.
3. **Si exit 0 et `output_summary` commence par `silence (no csv)`** : `data/outbound/inbox/leads.csv` absent. Pas de leads à enrichir, le founder doit en ajouter (à la main ou via ProspectMiner).
4. **Si exit 0 et `new=0 already=N`** : tous les leads ont déjà leur fiche dans `data/outbound/enriched/`. Idempotence OK.
5. **Si exit 0 et `new > 0`** : nouvelles fiches Markdown générées avec BANT/persona/email guesses. Propose au founder de :
   - Inspecter `data/outbound/enriched/<slug>.md` pour les nouveaux entries.
   - Lancer `/run-outbound-bot` pour scaffold les séquences (et `/draft-outbound <slug>` pour drafter touch-by-touch).
6. **Si exit 1** : CSV invalide (colonnes manquantes ou domaine syntaxiquement faux). Lis l'erreur, corrige le CSV, relance.

## Notes

- Heuristiques offline uniquement (D-017) — pas d'API Apollo / Hunter / Clearbit.
- Le skill markdown `lead-enricher` (`.claude/skills/lead-enricher/`) reste invoqué par `/draft-outbound <slug>` pour affiner 1 lead en humain-in-the-loop. L'agent Python batch tout l'inbox sans interaction.
- BANT seuil de qualification = 40/100 (réutilisé par `/draft-outbound` pour refuser de drafter sous le seuil).
- Idempotent : si `<slug>.md` existe déjà, le bot ne touche pas (laisse les annotations manuelles intactes).
