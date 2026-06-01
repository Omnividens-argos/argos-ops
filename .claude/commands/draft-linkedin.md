---
description: Drafte un post LinkedIn organique Argos (1300-2000 chars) depuis un topic + la KB Argos. Hook ligne 1 → 3-4 paragraphes courts → CTA soft → 3-5 hashtags. Humain-in-the-loop. Local-draft — connecteur LinkedIn shadow tant que le token OAuth absent.
---

# /draft-linkedin

Slash command interactif pour drafter un post **LinkedIn** Argos (Sprint
contenu, D-017 local-first). Pas de cron — l'humain pilote chaque post pour
la qualité éditoriale.

Invoque le skill **`linkedin-writer`** ([SKILL.md](../skills/linkedin-writer/SKILL.md))
qui porte toute la logique éditoriale. Cette commande en est l'enveloppe.

## Usage

- `/draft-linkedin <topic>` — drafte un post sur le topic donné
- `/draft-linkedin <topic> --cta <url|texte>` — impose un CTA précis
- `/draft-linkedin` (sans argument) — propose 2-3 topics pertinents (mix
  produit / actu cyber / objection client) avec rationale, en regardant
  `data/content/drafts/` pour éviter de reposter le même angle

## Workflow (résumé — détail dans le SKILL)

1. **Validation input** — `topic` manquant → proposer 3 sujets ; vague →
   demander précision.
2. **Contexte KB** (non négociable) — `kb-rag` (top-5) + `tone_of_voice.md`
   + `ICP.md`, et conditionnellement `argos_features` / `competitor_compare`
   / `faq` / `pricing`.
3. **Drafting interactif** — angle (2-3 options) → hook ligne 1 → corps
   (3-4 paragraphes courts) → CTA soft → 3-5 hashtags. Recompter les chars
   (cible 1300-2000).
4. **Audit claude-judge** (AVANT écriture) — `channel='social_linkedin'`,
   `agent_name='ContentBot'`. Parser via `parse_judge_json` +
   `apply_thresholds`. `killed` → refuser + reformuler ; `queued` →
   `status: queued` + `judge_issues:` ; `auto_send` → `status: draft`.
5. **Validation + écriture** — preview + character_count + (judge_score /
   verdict). Refuser si hors 1300-2000 chars ou `killed`. Écrire dans
   `data/content/drafts/YYYY-MM-DD-linkedin-<slug>.md`.
6. **Posting** — manuel (copier-coller + maj frontmatter) ou auto via le
   publisher (`status: validated` + `scheduled_for`, posé par
   `content-scheduler`).

## Garde-fous (refuser fermement)

Génération sans KB · stats inventées · FUD vs concurrents · buzzwords
corporate (« game changer », « disruptif », « synergie ») · cascade d'emoji ·
CTA agressif · > 5 hashtags · mur de texte.

## Sortie attendue

Fichier `data/content/drafts/YYYY-MM-DD-linkedin-<slug>.md`, frontmatter +
body conformes à `.claude/skills/linkedin-writer/SKILL.md` § Output.

## Liens

- Skill : [`.claude/skills/linkedin-writer/SKILL.md`](../skills/linkedin-writer/SKILL.md)
- Connecteur : [`argos_ops/social/linkedin.py`](../../argos_ops/social/linkedin.py)
- KB : `data/knowledge_base/`
