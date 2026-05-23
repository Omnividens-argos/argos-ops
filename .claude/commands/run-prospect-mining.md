---
description: Lance ProspectMiner — append nouveaux prospects ICP à data/outbound/inbox/leads.csv depuis sources publiques (annonces légales, Crunchbase news, LinkedIn Jobs RSS). Idempotent.
---

# /run-prospect-mining

Slash command Claude Code invoquée manuellement ou par Task Scheduler (`argos-ops-prospect-mining`, cadence quotidienne 7h Paris) **sur l'ordi du fondateur** (D-017).

## Procédure

1. Lance `uv run python scripts/run_prospect_miner.py` (foreground, ~5-15 sec selon nombre de feeds).
2. Lis la sortie loguru et l'exit code.
3. **Si exit 0 et `output_summary` commence par `silence (no sources)`** : `data/sales/prospects/sources.yaml` absent ou vide. Propose au founder d'ajouter au moins une source.
4. **Si exit 0 et `output_summary` contient `new=0`** : aucun nouveau prospect (RSS stables / déjà tous dans l'inbox). Pas d'action.
5. **Si exit 0 et `new > 0`** : nouveaux leads appended à `data/outbound/inbox/leads.csv`. Propose au founder :
   - Lancer `/run-lead-enrich` pour enrichir les nouvelles fiches BANT.
   - Puis `/run-outbound-bot` pour scaffold les séquences cold email (shadow mode P13.A).
6. **Si exit 1** : erreur de lecture sources.yaml (mal formé) ou crash réseau hard. Lis le traceback.

## Notes

- Format `data/sales/prospects/sources.yaml` (toutes les clés optionnelles) :
  ```yaml
  manual:
    - full_name: "Marc Dupont"
      company: "Acme SA"
      domain: "acme.fr"
      title_hint: "CISO"
  annonces_legales:
    - "https://www.bodacc.fr/.../rss"
  crunchbase_news:
    - "https://news.crunchbase.com/feed/"
  linkedin_jobs:
    - "https://www.linkedin.com/jobs/search/.../public.rss"
  ```
- Le bot n'écrit que les leads avec `full_name` + `domain` valides. Les annonces RSS qui n'extraient pas le domaine remontent dans `by_source` mais ne polluent pas l'inbox.
- Conformité D-016 : aucun scraping HTML LinkedIn. Uniquement les RSS auth-free.
- Breaker associé : `ProspectMiner` (P15). Si trip, runtime check skip l'agent.
