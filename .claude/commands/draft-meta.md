---
description: Drafte un post Facebook Page Argos (~300-500 chars) pour un public TPE/PME non-technique (« Patrick »). Ton simple, rassurant, zéro jargon, anti-FUD strict, CTA offre d'entrée. Humain-in-the-loop. Local-draft — connecteur Meta shadow tant que META_PAGE_* absent.
---

# /draft-meta

Slash command interactif pour drafter un **post Facebook Page** Argos
(Sprint contenu, D-017 local-first). C'est le seul canal qui vise **les
patrons de TPE/PME non-techniques**, pas le persona cyber-expert des autres
writers. L'humain pilote chaque post.

Invoque le skill **`meta-writer`** ([SKILL.md](../skills/meta-writer/SKILL.md))
qui porte toute la logique éditoriale (persona « Patrick », anti-FUD, zéro
jargon). Cette commande en est l'enveloppe.

## Usage

- `/draft-meta <topic>` — drafte un post sur le topic
- `/draft-meta <topic> --cta <url>` — impose le lien CTA
- `/draft-meta` (sans argument) — propose 2-3 sujets TPE-friendly

## Workflow (résumé — détail dans le SKILL)

1. **Validation input** — `topic` trop technique → le reformuler en
   préoccupation Patrick avant d'écrire.
2. **Contexte KB pour les FAITS** — `kb-rag` + `pricing.md` (tier d'entrée
   Free/Pro UNIQUEMENT) + `faq.md` + `argos_features.md`. **Traduire** en
   grand public, ne jamais copier une phrase technique de la KB.
3. **Drafting interactif** — angle (toujours côté réassurance) → hook
   (préoccupation douce ou question, jamais dramatisée) → corps (1-3 phrases
   simples, métaphore grand public) → CTA doux (offre d'entrée) → 1-2 emoji
   grand public max. Cible 300-500 chars.
4. **Audit claude-judge** (AVANT écriture) — `channel='social_meta'`,
   `agent_name='ContentBot'`. Parser via `parse_judge_json` +
   `apply_thresholds`. Ici le juge surveille surtout **tone (FUD)** et
   **factual (capacité inventée)**. `killed` → reformuler ; `queued` →
   `status: queued` + `judge_issues:` ; `auto_send` → `status: draft`.
5. **Validation + écriture** — preview + character_count + (judge_score /
   verdict). Refuser si > 500 chars ou `killed`. Écrire dans
   `data/content/drafts/YYYY-MM-DD-meta-<slug>.md`.
6. **Posting** — manuel (copier-coller dans la Page + maj frontmatter) ou
   auto via le publisher (`status: validated` + `scheduled_for`). Connecteur
   `argos_ops/social/meta.py` shadow tant que `META_PAGE_*` absents (setup :
   token de Page via Meta Business Suite, scope `pages_manage_posts`).

## Garde-fous (refuser fermement)

- **FUD / peur** — jamais « votre site va se faire pirater ». Reformuler
  côté réassurance (« savez-vous si votre site est protégé ? »).
- **Jargon** — DAST / OWASP / CVE / pentest / vulnérabilité… → grand public.
- **Stats anxiogènes inventées** · **capacité produit inventée** (coller KB).
- **CTA enterprise** (Pro Max / Custom) — ici c'est Free / Pro 39€.
- **Pavé** (> 500 chars) · **cascade d'emoji**.

## Sortie attendue

Fichier `data/content/drafts/YYYY-MM-DD-meta-<slug>.md`, frontmatter + body
conformes à `.claude/skills/meta-writer/SKILL.md` § Output.

## Liens

- Skill : [`.claude/skills/meta-writer/SKILL.md`](../skills/meta-writer/SKILL.md)
- Connecteur : [`argos_ops/social/meta.py`](../../argos_ops/social/meta.py)
- Setup : Meta Business Suite (token de Page, scope `pages_manage_posts`)
- Script test : [`scripts/test_meta.py`](../../scripts/test_meta.py)
