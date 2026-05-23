# ⚠️ Fichier obsolète

> Ce fichier est **supprimé en tant que source d'avancement** depuis le
> 2026-05-23 (PR `chore/state-tracking-cleanup`). Il reste comme stub
> pour conserver les liens entrants qui pointaient ici.

## Où trouver l'état d'avancement maintenant

**Source unique** : [`ARGOS_OPS_PLAN.md` — Annexe D](ARGOS_OPS_PLAN.md#annexe-d--catalogue-cible--12-services--79-bots).

L'Annexe D liste les 79 bots cibles avec une checkbox par bot :
- `[x] ✅` — livré et actif
- `[~] 🟡` — partiel (skill / shadow mode livré, pas en cron)
- `[ ] ⬜` — roadmap

Le compteur global (`X livrés / Y roadmap`) est en tête de l'annexe.

## Pourquoi ce changement

Avant la refonte, l'avancement était dupliqué dans 3 fichiers
(CLAUDE.md, PROGRESS.md, ARGOS_OPS_PLAN.md). Ça créait :

- des incohérences entre les 3 sources,
- des merge conflicts à chaque session parallèle qui voulait mettre à
  jour CLAUDE.md / PROGRESS.md,
- une dette de maintenance (3 fichiers à synchroniser à chaque livraison).

Désormais : **1 seule source** (Annexe D du plan), cochée à la livraison.
`CLAUDE.md` est stable (invariants seulement).
