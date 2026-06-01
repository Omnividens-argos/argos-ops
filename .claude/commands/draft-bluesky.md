---
description: Drafte un post Bluesky (≤300 graphemes) depuis un topic + la KB Argos. Ton tech early-adopters / infosec, hook punchy + #infosec/#cyber, CTA optionnel. Humain-in-the-loop. Local-draft — le connecteur AT Protocol reste shadow tant que BLUESKY_HANDLE/APP_PASSWORD absents.
---

# /draft-bluesky

Slash command interactif pour drafter un post **Bluesky** Argos (Sprint
contenu, D-017 local-first). Bluesky est le canal social **100 % gratuit**
(API AT Protocol illimitée, un app password suffit). Pas de cron —
l'humain pilote chaque post pour la qualité éditoriale et le respect du
ton de la communauté tech.

Invoque le skill **`bluesky-writer`** ([SKILL.md](../skills/bluesky-writer/SKILL.md))
qui porte toute la logique éditoriale. Cette commande en est l'enveloppe.

## Usage

- `/draft-bluesky <topic>` — drafte un post sur le topic donné
- `/draft-bluesky <topic> --cta <url>` — impose un CTA précis
- `/draft-bluesky` (sans argument) — propose 2-3 topics pertinents (mix
  produit / actu cyber / objection client) avec rationale court, en
  regardant `data/content/drafts/` pour éviter de reposter le même angle

## Workflow (résumé — détail dans le SKILL)

### 1. Validation de l'input

- Si `topic` manquant → proposer 3 sujets pertinents avec rationale.
- Si `topic` vague (« cybersécurité », « la tech ») → demander une
  précision : un bon post Bluesky part d'une idée nette.

### 2. Chargement contexte KB (non négociable)

Invoquer `kb-rag` (P6) avec `topic` (top-5 chunks). Charger en plus :
`data/knowledge_base/tone_of_voice.md` + `ICP.md`. Conditionnellement
selon le topic : `argos_features.md`, `competitor_compare.md`, `faq.md`,
`pricing.md`. Sans KB, on retombe dans le ton générique IA — refuser.

### 3. Drafting interactif

Proposer + faire valider : **angle** (2-3 options) → **hook** (ligne 1) →
**corps** (1-2 phrases denses) → **CTA** (soft, optionnel) → **hashtags**
(1-3, dont `#infosec` ou `#cyber`). Recompter les graphemes à chaque
itération ; si > 300, raccourcir avant d'avancer.

### 4. Audit agent-juge (claude-judge, P14) — AVANT écriture

Invoquer `claude-judge` avec : `draft=body` + `original_query=topic` +
`rag_chunks` (étape 2) + `channel='social_bluesky'` +
`agent_name='ContentBot'`.

```python
from argos_ops.judge import parse_judge_json, apply_thresholds
report = parse_judge_json(judge_output_text)
verdict = apply_thresholds(report)
```

- `verdict='killed'` → **refuser** d'écrire, montrer les issues, proposer
  une reformulation ciblée (factual / tone / legal).
- `verdict='queued'` → écrire avec `status: queued` + `judge_issues:`.
- `verdict='auto_send'` → écrire avec `status: draft`.

Toujours écrire `judge_score`, `judge_verdict`, `judge_rationale` au
frontmatter, quel que soit le verdict.

### 5. Validation finale + écriture

- Preview du post complet avec **character_count** + **(judge_score /
  verdict)**.
- Refuser d'écrire si > 300 graphemes ou `verdict='killed'`.
- Demander confirmation, puis écrire avec `Write` dans
  `data/content/drafts/YYYY-MM-DD-bluesky-<slug>.md`.

### 6. Posting (jusqu'au ContentBot full)

Le connecteur `argos_ops/social/bluesky.py` est en **shadow** tant que
`BLUESKY_HANDLE` + `BLUESKY_APP_PASSWORD` sont absents de `.env.local`
(setup : bsky.app → Settings → App Passwords).

- **Manuel** : copier-coller dans https://bsky.app, puis éditer le
  frontmatter : `status: posted` + `posted_at:` + `url_posted:`.
- **Test live** (credentials remplis) :
  `uv run python scripts/test_bluesky.py --message "<body>"`.

## Garde-fous (refuser fermement)

- **Génération sans KB** — risque ton générique IA.
- **Stats inventées** — toute stat chiffrée doit avoir une source réelle.
  Sur Bluesky (audience experte), une stat bidon coûte la crédibilité.
- **FUD vs concurrents** — respect strict de `competitor_compare.md`
  § anti-disparagement.
- **Buzzwords corporate** — « game changer », « disruptif », « synergie ».
- **Hook mou** — « petit thread sur la sécu 🧵 ». Le hook livre une idée.
- **Sur-tagging** (4+ hashtags) et **cascade d'emoji** (🚀🔥💯).
- **> 300 graphemes** — réécrire plus court, ne pas tronquer brutalement.

## Sortie attendue

Fichier `data/content/drafts/YYYY-MM-DD-bluesky-<slug>.md`, frontmatter +
body conformes à `.claude/skills/bluesky-writer/SKILL.md` § Output.
Status initial : `draft` (ou `queued` si le juge le demande).

## Test plan

- [ ] `/draft-bluesky "oracle reproductible vs faux positifs"` → draft
      ≤300 graphemes, hashtag #infosec/#cyber, kb_sources non vide.
- [ ] `/draft-bluesky` sans argument → propose des (topics) cohérents vs
      l'historique des drafts.
- [ ] Demander « invente une stat » → refus + alternative.
- [ ] Vérifier qu'un body > 300 graphemes déclenche un raccourcissement,
      pas une écriture tronquée.

## Liens

- Skill : [`.claude/skills/bluesky-writer/SKILL.md`](../skills/bluesky-writer/SKILL.md)
- Connecteur : [`argos_ops/social/bluesky.py`](../../argos_ops/social/bluesky.py)
- Setup : bsky.app → Settings → App Passwords
- Script test live : [`scripts/test_bluesky.py`](../../scripts/test_bluesky.py)
- KB : `data/knowledge_base/`
