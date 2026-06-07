---
description: Lance MemoryCurator — nettoie la mémoire de flotte (archive le périmé TTL + stale, purge le très vieux, protège l'important). Silence Discord si rien à nettoyer.
---

# /run-memory-curator

Slash command Claude Code invoquée manuellement ou par Task Scheduler
(`argos-ops-memory-curator`, hebdo dimanche 4h) **sur l'ordi du fondateur**
(D-017). Concierge de la mémoire de flotte (`data/fleet_memory/`).

## Procédure

1. Lance `uv run python scripts/run_memory_curator.py` (foreground, ~1 sec).
2. Lis la sortie loguru et l'exit code.
3. **Si exit 0 et `output_summary` commence par `silence (vert)`** : rien à
   nettoyer, mémoire saine.
4. **Si exit 0 et `output_summary` commence par `alert pushed`** : un embed
   jaune a été poussé. Lis le summary (ex : `3 archivé(s) · 1 supprimé(s) ·
   5 important(s) protégé(s) · 42 fait(s) inspecté(s)`).
5. **Si exit 0 et `output_summary` commence par `alerte non envoyée`** :
   webhook `DISCORD_WEBHOOK_OPS_LOGS` absent (le nettoyage a quand même eu lieu).

## Politique (déterministe, aucun LLM — D-017)

- **TTL** : fait actif dont `ttl_days` est dépassé → **archivé** (soft delete).
- **Stale** : fait actif sans TTL plus vieux que 365 j → **archivé**.
- **Purge** : fait **déjà archivé** depuis > 90 j → **supprimé** (hard delete,
  libère le disque). Cycle de vie en 2 temps = filet de sécurité.
- **Pinned** : un fait `pinned: true` (« jugé important ») n'est **jamais**
  touché, quel que soit son âge.

## Notes

- Les doublons exacts sont impossibles par construction (l'`id` d'un fait =
  empreinte de son corps). La dédup sémantique (paraphrases) est hors périmètre
  (pas d'embeddings sur la mémoire — D-017).
- Seuils ajustables à l'instanciation (`MemoryCurator(stale_active_days=...,
  purge_archived_days=...)`). Mettre un seuil à `None` désactive l'étape.
- C'est le **seul** bot autorisé à supprimer définitivement un fait
  (`fleet_memory.delete_fact`).
