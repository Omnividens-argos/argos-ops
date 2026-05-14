---
description: Drafte 3 variantes d'annonce Ads (Google Search RSA / LinkedIn Sponsored / Meta) avec audit claude-judge. Humain-in-the-loop. Mode shadow uniquement — posting manuel jusqu'à P12.B (live mode).
---

# /draft-ad

Slash command interactif pour drafter une annonce Ads Argos (P12 shadow,
D-017). Pas de cron — le fondateur pilote chaque draft. Pas de publication
API tant qu'un budget pub n'est pas activé.

## Usage

- `/draft-ad <platform> <objective> <persona>` — drafte 3 variantes
- `/draft-ad <platform> <objective>` — propose un persona pertinent
- `/draft-ad <platform>` — propose un (objective, persona) cohérent avec
  l'historique `data/ads/drafts/`
- `/draft-ad` — propose un (platform, objective, persona) selon priorité
  pipeline Argos

Plateformes : `google_search`, `linkedin_sponsored`, `meta_image`.
Objectifs : `awareness`, `consideration`, `leads`, `demo`.
Personas : `marc` (sécu in-house), `sarah` (lead dev / CTO), `thomas` (MSP).

## Workflow

### 1. Validation des inputs

- Si `platform` manquant ou hors liste → demander.
- Si `objective` manquant → demander (impact direct sur le CTA).
- Si `persona` manquant → proposer selon `keyword` (Marc pour audit/pentest,
  Sarah pour DevSecOps/CI, Thomas pour MSP/multi-clients).
- Si `platform=meta_image` → rappeler que c'est canal **bas priorité** pour
  BtoB Argos et demander confirmation avant de drafter.

### 2. Chargement contexte KB

Invoquer `kb-rag` (P6) avec `objective + persona`. Charger systématiquement :

- `data/knowledge_base/tone_of_voice.md`
- `data/knowledge_base/ICP.md`
- `data/knowledge_base/argos_features.md` (différenciants)
- `data/knowledge_base/competitor_compare.md` (règles anti-disparagement § 10)

### 3. Drafting interactif — 3 variantes diversifiées

Proposer **3 angles différents** (pas paraphrases) :

- **A — Tech-first** : différenciant produit (oracle, modules, preuve)
- **B — Bénéfice ops** : ROI temps équipe, coût FP, CI/CD
- **C — Risque légitime** : OWASP / compliance ; AUCUN FUD

Pour chaque variante :
- **Compter les caractères** au fur et à mesure
- **Refuser** si une contrainte plateforme est violée (tableau dans
  `.claude/skills/ads-creative-writer/SKILL.md` § « Plateformes supportées »)

### 4. Audit agent-juge (P14) — pour CHAQUE variante

Invoquer `claude-judge` avec `draft = bloc variante complet` +
`channel = 'ads_<platform>'` + `agent_name = 'AdBot'` + `rag_chunks`.

Parse via :

```python
from argos_ops.judge import parse_judge_json, apply_thresholds
report = parse_judge_json(judge_output_text)
verdict = apply_thresholds(report)
```

- Variante `killed` → ne l'inclus PAS dans le draft final. Re-propose
  une 4e variante en corrigeant l'axe défaillant.
- Variante `queued` → garde, flag les issues dans le frontmatter
  (`judge_issues_<A|B|C>:`).
- Variante `auto_send` → garde.

### 5. Validation finale + écriture

- Preview les 3 variantes (ou 2 si une killed) avec :
  - character_count par champ
  - `(judge_score / verdict)` par variante
  - Indication explicite des contraintes plateforme respectées
- **Refuser d'écrire** si toutes les variantes sont `killed`. Re-loop step 3.
- Demander : « OK pour écrire dans `data/ads/drafts/<filename>.md` ? »
- Si oui : `Write` tool, slug = kebab-case de `<objective>-<persona>` tronqué
  50 chars, date = aujourd'hui (TZ Paris).

### 6. Suivi posting manuel

Rappeler au fondateur (jusqu'à P12.B live mode) :

> Une fois publié en plateforme, édite le frontmatter du draft :
> - `status: live`
> - `posted_at: YYYY-MM-DDTHH:MM`
> - `posted_campaign_id: <id Google Ads / LinkedIn / Meta>`

Quand le CSV de perf semaine N+1 arrive, `/analyze-ads` pourra référencer
ce campaign_id pour le calcul ROAS.

### 7. Notif Discord

Pousser sur `DISCORD_WEBHOOK_OPS_LOGS` si configuré :
« Ad creative draft livré : [<platform>] <objective>/<persona> ·
3 variantes · `data/ads/drafts/<file>` ».

## Garde-fous (refuser fermement)

- **Génération sans KB** — refuser, expliquer le risque ton générique IA.
- **3 variantes paraphrasées** — refuser, exiger angles vraiment différents.
- **Stats inventées** — chiffres → source réelle obligatoire. Sinon retirer.
- **FUD vs concurrent nommé** — refuser (Google Ads peut rejeter en plus
  pour publicité comparative non encadrée).
- **Superlatifs Google-bannis** — « le meilleur », « numéro 1 », « 100 % » → refus.
- **Buzzwords corporate** — « innovant », « disruptif », « game changer ».
- **Cross-platform identique** — refuser le même texte sur Google et LinkedIn.
  Chaque plateforme exige une formulation propre.

## Sortie attendue

Fichier `data/ads/drafts/YYYY-MM-DD-<platform>-<slug>.md` avec frontmatter
+ 3 variantes (A/B/C) prêtes à copier-coller dans Google Ads Editor /
LinkedIn Campaign Manager / Meta Ads Manager.

Status initial : `draft`. Le fondateur le passe à `validated` puis `live`
manuellement.

## Test plan (à dérouler en P12 closure)

- [ ] `/draft-ad google_search leads marc` → 3 variantes RSA générées,
      headlines ≤ 30 chars, descriptions ≤ 90 chars, kb_sources non vide
- [ ] `/draft-ad linkedin_sponsored awareness sarah` → 1 headline ≤ 150
      chars + 1 intro ≤ 600 chars + suggestion image documentée
- [ ] `/draft-ad meta_image leads marc` → confirmation explicite demandée
      (canal bas priorité BtoB)
- [ ] Garde-fou stat inventée → refus + proposition d'alternative
- [ ] Garde-fou FUD vs Burp → refus + reformulation factuelle

## Liens

- Skill : `.claude/skills/ads-creative-writer/SKILL.md`
- Skill cousin : `.claude/skills/ads-optimizer/SKILL.md` (analyse perf)
- Slash command cousin : `/analyze-ads` (analyse CSV → recommandations)
- Drafts : `data/ads/drafts/`
- Plan P12 full : `docs/ARGOS_OPS_PLAN.md` § Partie 12
