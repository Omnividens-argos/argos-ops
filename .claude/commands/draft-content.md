---
description: Dispatcher multi-canal (déprécié au profit des slashs dédiés) — route vers /draft-linkedin, /draft-mastodon ou /draft-bluesky selon le canal demandé. Préférer directement le slash du canal voulu.
---

# /draft-content (dispatcher — préférer les slashs dédiés)

> **Depuis le Sprint contenu (2026-06-01), chaque canal a son slash dédié.**
> Cette commande est conservée comme **aiguillage** : elle ne drafte plus
> elle-même, elle te route vers le bon skill mono-canal. Pour aller plus
> vite, invoque directement :
>
> | Canal | Slash | Skill |
> |-------|-------|-------|
> | LinkedIn | `/draft-linkedin` | `linkedin-writer` |
> | Mastodon | `/draft-mastodon` | `mastodon-writer` |
> | Bluesky | `/draft-bluesky` | `bluesky-writer` |

## Comportement

À partir de `/draft-content <channel> <topic>` :

1. **Lis le `channel`** :
   - `linkedin` → invoque le skill **`linkedin-writer`** avec `<topic>`.
   - `mastodon` → invoque le skill **`mastodon-writer`** avec `<topic>`.
   - `bluesky` → invoque le skill **`bluesky-writer`** avec `<topic>`.
   - `x` / `twitter` → pas encore de writer dédié (canal bas priorité,
     D-004). Proposer LinkedIn/Mastodon/Bluesky à la place, ou drafter à la
     main si vraiment voulu.
   - `reddit` → **refuser** : retiré du périmètre par
     [D-022](../../docs/DECISIONS.md#d-022--retrait-d%C3%A9finitif-de-reddit-du-p%C3%A9rim%C3%A8tre-argos-ops)
     (2026-05-15).
2. **Channel manquant** → demander lequel (linkedin / mastodon / bluesky),
   puis router.

Toute la logique éditoriale (charge KB via `kb-rag`, drafting interactif,
audit `claude-judge`, écriture dans `data/content/drafts/`) vit désormais
dans le skill du canal — cf. son `SKILL.md`.

## Pourquoi ce changement

Un réseau a sa physique propre (longueur, format, tonalité, règles
communautaires). Un skill mono-canal produit un meilleur post qu'un skill
fourre-tout. L'ancien skill `content-writer` est déprécié (cf.
`.claude/skills/content-writer/SKILL.md`).

## Liens

- `/draft-linkedin` · `/draft-mastodon` · `/draft-bluesky`
- Skills : `linkedin-writer`, `mastodon-writer`, `bluesky-writer`
- Planif : `content-scheduler` (pose `scheduled_for`)
