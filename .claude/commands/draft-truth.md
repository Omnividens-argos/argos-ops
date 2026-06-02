---
description: Drafte un post Truth Social (fork Mastodon, ≤500 chars) — canal expérimental bas priorité. Règle n°1 = brand safety apolitique stricte, sécurité grand public neutre. Humain-in-the-loop. DRAFT-ONLY — connecteur shadow tant que TRUTH_SOCIAL_ACCESS_TOKEN absent (accès API à demander).
---

# /draft-truth

Slash command interactif pour drafter un **post Truth Social** Argos (Sprint
contenu, D-017 local-first).

> ⚠️ **Canal le plus expérimental / bas priorité.** Truth Social = plateforme
> US généraliste/politique, audience ~0 overlap avec l'ICP Argos (cyber FR).
> **DRAFT-ONLY** : accès API à demander par le fondateur, connecteur en
> shadow. Si le user hésite à investir ce canal, dis-le franchement.

Invoque le skill **`truth-social-writer`** ([SKILL.md](../skills/truth-social-writer/SKILL.md)).

## Règle n°1 — brand safety

**Zéro contenu politique / partisan / culture-war.** Uniquement de la
sensibilisation **sécurité grand public neutre**, intemporelle, applicable à
n'importe qui. Au moindre doute de neutralité → ne pas écrire. C'est le
garde-fou qui prime sur tout le reste.

## Usage

- `/draft-truth <topic>` — drafte un post (topic neutre uniquement)
- `/draft-truth` — propose 2-3 angles neutres

## Workflow (résumé — détail dans le SKILL)

1. **Validation input** — topic à coloration politique → **refuser** +
   proposer un angle sécurité neutre.
2. **Contexte KB** — `kb-rag` (top-5) + `tone_of_voice.md` + (selon topic)
   `faq.md` / `pricing.md` / `argos_features.md`. Traduire en grand public
   neutre.
3. **Drafting interactif** — angle neutre → hook utile → corps (anglais en
   général, 1-3 phrases) → lien/hashtag neutres optionnels. Recompter (≤ 500).
4. **Audit claude-judge** (AVANT écriture) — `channel='social_truth'`,
   `agent_name='ContentBot'`. Parser via `parse_judge_json` +
   `apply_thresholds`. `killed` → reformuler ; `queued` → `status: queued`
   + `judge_issues:` ; `auto_send` → `status: draft`.
5. **Validation + écriture** — preview + character_count (≤ 500) +
   (judge_score / verdict). Refuser si > 500, `killed`, ou doute de
   neutralité. Écrire dans `data/content/drafts/YYYY-MM-DD-truth-<slug>.md`.
6. **Posting** — manuel (copier-coller + maj frontmatter). Auto plus tard via
   le connecteur une fois `TRUTH_SOCIAL_ACCESS_TOKEN` rempli.

## Garde-fous (refuser fermement)

**Tout contenu politique / partisan / culture-war** (règle n°1) · hook mou ·
génération sans KB · FUD · stats inventées · jargon cyber pointu · buzzwords ·
> 500 chars · cascade d'emoji · hashtag militant.

## Sortie attendue

Fichier `data/content/drafts/YYYY-MM-DD-truth-<slug>.md`, frontmatter + body
conformes à `.claude/skills/truth-social-writer/SKILL.md` § Output.

## Liens

- Skill : [`.claude/skills/truth-social-writer/SKILL.md`](../skills/truth-social-writer/SKILL.md)
- Connecteur : [`argos_ops/social/truth_social.py`](../../argos_ops/social/truth_social.py)
- Setup : section `# --- Truth Social ---` de `.env.example`
- Script test : [`scripts/test_truth_social.py`](../../scripts/test_truth_social.py)
