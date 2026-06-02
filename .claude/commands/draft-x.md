---
description: Drafte un post X (ex-Twitter) ≤280 chars pour la cyber-Twitter. Hook viral ligne 1, ton punchy, 0-1 hashtag. Humain-in-the-loop. DRAFT-ONLY — connecteur X shadow tant que X_ACCESS_TOKEN absent, activation live reportée (arbitrage Free vs Basic).
---

# /draft-x

Slash command interactif pour drafter un **post X (ex-Twitter)** Argos
(Sprint contenu, D-017 local-first), pour la **cyber-Twitter** (infosec).

> **Canal bas priorité + DRAFT-ONLY** : le connecteur
> `argos_ops/social/twitter.py` reste en shadow et l'activation live est
> reportée (le fondateur arbitrera Free vs Basic côté API X). On drafte
> maintenant, on postera plus tard.

Invoque le skill **`x-writer`** ([SKILL.md](../skills/x-writer/SKILL.md))
qui porte toute la logique éditoriale.

## Usage

- `/draft-x <topic>` — drafte un tweet sur le topic
- `/draft-x <topic> --cta <url>` — impose un lien (compté ~23 chars)
- `/draft-x` (sans argument) — propose 2-3 angles à fort hook

## Workflow (résumé — détail dans le SKILL)

1. **Validation input** — topic vague → demander précision (un tweet part
   d'une idée tranchée).
2. **Contexte KB** — `kb-rag` (top-5) + `tone_of_voice.md` + `ICP.md`, et
   conditionnellement `argos_features` / `competitor_compare` / `faq`.
3. **Drafting interactif** — angle (jugé sur son hook) → hook ligne 1
   (le plus travaillé) → corps nerveux (1-2 phrases) → lien/hashtag
   optionnels (lien = ~23 chars, 0-1 hashtag). Recompter (≤ 280).
4. **Audit claude-judge** (AVANT écriture) — `channel='social_x'`,
   `agent_name='ContentBot'`. Parser via `parse_judge_json` +
   `apply_thresholds`. `killed` → reformuler ; `queued` → `status: queued`
   + `judge_issues:` ; `auto_send` → `status: draft`.
5. **Validation + écriture** — preview + character_count (≤ 280) +
   (judge_score / verdict). Refuser si > 280 ou `killed`. Écrire dans
   `data/content/drafts/YYYY-MM-DD-x-<slug>.md`.
6. **Posting** — manuel (copier-coller sur X + maj frontmatter). Auto plus
   tard via le connecteur une fois `X_ACCESS_TOKEN` rempli et le live activé.

## Garde-fous (refuser fermement)

Hook mou (« petit thread 🧵 ») · génération sans KB · **FUD** (le vendor
anxiogène est le cliché qu'on méprise, cf. `tone_of_voice.md`) · stats
inventées · FUD vs concurrents · buzzwords corporate · cascade d'emoji ·
2+ hashtags · > 280 chars.

## Sortie attendue

Fichier `data/content/drafts/YYYY-MM-DD-x-<slug>.md`, frontmatter + body
conformes à `.claude/skills/x-writer/SKILL.md` § Output.

## Liens

- Skill : [`.claude/skills/x-writer/SKILL.md`](../skills/x-writer/SKILL.md)
- Connecteur : [`argos_ops/social/twitter.py`](../../argos_ops/social/twitter.py)
- Setup : section `# --- X / Twitter ---` de `.env.example`
- Script test : [`scripts/test_twitter.py`](../../scripts/test_twitter.py)
