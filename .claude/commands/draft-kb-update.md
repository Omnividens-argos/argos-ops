---
description: Lance KBUpdater — détecte les gaps KB depuis tickets répétés et drafte un squelette d'article par thème. Humain peaufine via kb-rag + claude-judge.
---

# /draft-kb-update

Slash command Claude Code invoquée manuellement (hebdo recommandé) sur l'ordi du fondateur (D-017).

## Procédure

1. Lance `uv run python scripts/run_kb_updater.py`.
2. **Si exit 0 et `silence (no tickets)`** : `data/support/tickets.yaml` absent. Le founder doit logger ses tickets résolus à la main (ou via EmailBot quand /run-ticket-triage tournera).
3. **Si exit 0 et `drafted > 0`** : embed Discord jaune posté avec top gaps.
4. **Pour chaque draft `data/knowledge_base/drafts/<slug>.md`** :
   - Invoque `kb-rag` pour vérifier qu'aucun article existant ne couvre déjà le sujet (similarity > 0.7 = doublon, à fusionner).
   - Peaufine les sections Symptôme / Cause / Fix / Prévention à partir des tickets sources.
   - Invoque `claude-judge` pour audit factual (anti-hallucination) + tone + legal.
   - Si OK : `mv data/knowledge_base/drafts/<slug>.md data/knowledge_base/<slug>.md` puis `uv run python scripts/seed_kb.py` pour réindexer.

## Notes

- Format `data/support/tickets.yaml` :
  ```yaml
  tickets:
    - ticket_id: "TCK-2026-0042"
      customer_id: "acme-sa"
      subject: "Scan bloque sur /api"
      body: "Le scan ne finit jamais quand on cible l'API GraphQL..."
      opened_at: "2026-05-20"
      plan: "pro"
      status: "resolved"
  ```
- Clustering par mots-clés sujet (4 lettres min, stop-words filtrés).
- Seuil `MIN_OCCURRENCES = 2` — un thème vu 2x déclenche un draft.
- Idempotent : un draft existant ou un article KB existant (même slug) n'est pas recréé.
- Skill réutilisé : `kb-rag` (P6), `claude-judge` (P14).
- Breaker associé : `KBUpdater` (P15).
