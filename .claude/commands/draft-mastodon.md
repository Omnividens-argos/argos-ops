---
description: Drafte un toot Mastodon Argos (300-500 chars, infosec.exchange) depuis un topic + la KB Argos. Partage technique d'abord, 2-3 hashtags, lien en fin. Humain-in-the-loop. Local-draft — connecteur Mastodon shadow tant que MASTODON_ACCESS_TOKEN absent.
---

# /draft-mastodon

Slash command interactif pour drafter un **toot Mastodon** Argos sur
`infosec.exchange` (Sprint contenu, D-017 local-first). Pas de cron —
l'humain pilote chaque toot pour respecter la culture technique de
l'instance.

Invoque le skill **`mastodon-writer`** ([SKILL.md](../skills/mastodon-writer/SKILL.md))
qui porte toute la logique éditoriale. Cette commande en est l'enveloppe.

## Usage

- `/draft-mastodon <topic>` — drafte un toot sur le topic donné
- `/draft-mastodon <topic> --cta <url>` — impose un lien précis (feature/blog)
- `/draft-mastodon` (sans argument) — propose 2-3 topics techniques
  pertinents avec rationale, en regardant `data/content/drafts/`

## Workflow (résumé — détail dans le SKILL)

1. **Validation input** — `topic` manquant → proposer 3 sujets ; vague →
   demander précision.
2. **Contexte KB** (non négociable) — `kb-rag` (top-5) + `tone_of_voice.md`
   + `ICP.md`, et conditionnellement `argos_features` / `competitor_compare`
   / `faq`.
   **Mémoire de flotte** (non négociable) — lancer
   `uv run python scripts/fleet_memory_in.py MastodonWriter` et injecter les
   faits actifs (tendances TrendSpotter…) dans le contexte de drafting.
3. **Drafting interactif** — angle (partage technique > promo) → hook
   technique → corps (1-2 paragraphes denses) → lien en fin (feature/blog,
   pas démo) → 2-3 hashtags. Recompter les chars (cible 300-500).
4. **Audit claude-judge** (AVANT écriture) — `channel='social_mastodon'`,
   `agent_name='ContentBot'`. Parser via `parse_judge_json` +
   `apply_thresholds`. `killed` → refuser + reformuler ; `queued` →
   `status: queued` + `judge_issues:` ; `auto_send` → `status: draft`.
5. **Validation + écriture** — preview + character_count + (judge_score /
   verdict). Refuser si hors 300-500 chars ou `killed`. Écrire dans
   `data/content/drafts/YYYY-MM-DD-mastodon-<slug>.md`.
6. **Posting** — manuel (copier-coller + maj frontmatter) ou auto via le
   publisher (`status: validated` + `scheduled_for`, posé par
   `content-scheduler`).

## Garde-fous (refuser fermement)

Génération sans KB · promo directe en tête (partage technique d'abord) ·
stats inventées · FUD vs concurrents · buzzwords corporate · **tout** emoji
marketing (zéro sur Mastodon) · lien démo en tête · > 500 chars.

## Sortie attendue

Fichier `data/content/drafts/YYYY-MM-DD-mastodon-<slug>.md`, frontmatter +
body conformes à `.claude/skills/mastodon-writer/SKILL.md` § Output.

## Liens

- Skill : [`.claude/skills/mastodon-writer/SKILL.md`](../skills/mastodon-writer/SKILL.md)
- Connecteur : [`argos_ops/social/mastodon.py`](../../argos_ops/social/mastodon.py)
- KB : `data/knowledge_base/`
