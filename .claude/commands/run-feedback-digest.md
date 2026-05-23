---
description: Lance FeedbackAggregator — agrège les demandes clients par thème depuis data/feedback/items.yaml. Écrit un digest Markdown + Discord top demandes.
---

# /run-feedback-digest

Slash command Claude Code invoquée manuellement (hebdo recommandé) ou Task Scheduler.

## Procédure

1. Le founder ajoute manuellement les items dans `data/feedback/items.yaml` (au fil des conversations clients / emails / Discord).
2. Lance `uv run python scripts/run_feedback_aggregator.py`.
3. **Si `silence (no items)`** : items.yaml vide.
4. **Si `themes > 0`** : Discord jaune avec top 5 demandes. Lis `data/feedback/digest_<date>.md` pour les détails.

## Notes

- Format `data/feedback/items.yaml` :
  ```yaml
  items:
    - source: "email"            # email | support | discord | call
      customer_id: "acme-sa"
      date: "2026-05-18"
      topic: "Export PDF en français"
      verbatim: "On aimerait avoir l'export rapport disponible en FR."
  ```
- Clustering exact sur le champ `topic` (pas de NLP — le founder normalise lui-même les libellés).
- Sortie : digest Markdown classé par fréquence décroissante. Sert d'input à l'arbitrage roadmap mensuel.
- Idempotent : digest du jour écrasé. Pour historique, archiver à la main.
- Breaker : `FeedbackAggregator` (P15).
