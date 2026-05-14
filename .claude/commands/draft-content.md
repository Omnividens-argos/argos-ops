---
description: Drafte un post social adapté à un canal (LinkedIn / Mastodon / Reddit / X) depuis un topic + la KB Argos. Humain-in-the-loop. Mode local-draft only — posting manuel jusqu'à P11.
---

# /draft-content

Slash command interactif pour drafter un post réseau social Argos (P9-DRAFT,
D-017). Pas de cron — l'humain pilote chaque post pour garantir la qualité
éditoriale et le respect des règles communautaires par canal (notamment
règle 9:1 r/netsec).

## Usage

- `/draft-content <channel> <topic>` — drafte un post sur le canal et le topic donnés
- `/draft-content <channel>` — propose 3 topics depuis l'actualité KB / pipeline
- `/draft-content` (sans argument) — propose un (canal, topic) optimal pour
  aujourd'hui (regarde `data/content/drafts/` pour éviter de poster 2× le même
  canal trop rapproché)

Canaux acceptés : `linkedin`, `mastodon`, `reddit`, `x`.

## Workflow

### 1. Validation des inputs

- Si `channel` manquant ou hors liste → demander lequel.
- Si `topic` manquant → proposer 3 sujets pertinents (mix produit /
  cybersec actu / objection client courante) avec rationale court.
- Si `channel=reddit` → demander **explicitement** : « Quelles sont tes
  dernières contributions non-promo sur r/netsec ? Règle 9:1 stricte. »
  Si réponse < 9 contributions récentes → refuser le draft promo et
  proposer plutôt une réponse technique à une question existante.

### 2. Chargement contexte KB

Invoquer le skill `kb-rag` (P6) avec `topic` (top-5 chunks). En complément,
charger systématiquement :

- `data/knowledge_base/tone_of_voice.md`
- `data/knowledge_base/ICP.md`

Et conditionnellement selon topic (cf. `content-writer/SKILL.md` § 2).

### 3. Drafting interactif (mode interview court)

Pour chaque post, **proposer** + **demander validation** :

1. **Angle** — 2-3 propositions d'angle avec rationale (« angle A traite
   l'objection X de Marc »).
2. **Hook / 1re ligne** — celle qui doit accrocher dans le feed.
3. **Corps** — adapter à la longueur du canal :
   - LinkedIn : 1300-2000 chars, 3-4 paragraphes courts
   - Mastodon : 300-500 chars, 1-2 paragraphes tech
   - Reddit : 800-2000 mots, longform technique sans pitch produit
   - X : ≤ 280 chars
4. **CTA** — soft, matché au canal. Reddit = **aucun CTA produit** dans
   le post initial (jamais de lien `omnividens.fr` direct).
5. **Hashtags** — appliquer le quota par canal.

### 4. Audit agent-juge (P14)

Avant écriture, invoque le skill `claude-judge` avec : `draft=body` +
`original_query=topic` + `rag_chunks` (du `kb-rag` étape 2) +
`channel='social_<canal>'` + `agent_name='ContentBot'`.

Parse :

```python
from argos_ops.judge import parse_judge_json, apply_thresholds
report = parse_judge_json(judge_output_text)
verdict = apply_thresholds(report)
```

Conséquences :

- `verdict='killed'` → **refuse** d'écrire le draft. Affiche les issues
  et propose une reformulation (corriger factual / tone / legal selon
  l'axe défaillant).
- `verdict='queued'` → écrit le draft avec `status: queued` au lieu de
  `draft`, et liste les issues à corriger dans le frontmatter
  (`judge_issues:`).
- `verdict='auto_send'` → continue avec `status: draft` (humain doit
  encore valider visuellement avant posting manuel).

Ajoute toujours `judge_score`, `judge_verdict`, `judge_rationale` au
frontmatter du draft écrit, peu importe le verdict, pour audit
ultérieur.

### 5. Validation finale + écriture

- Afficher le post complet en preview avec **character_count** /
  **word_count** calculés + **(judge_score / verdict)**.
- **Refuser d'écrire** si la contrainte longueur est dépassée ou si
  verdict=`killed`. Proposer une version corrigée.
- Demander : « OK pour écrire dans `data/content/drafts/<filename>.md` ? »
- Si oui, écrire avec le `Write` tool. Slug = kebab-case du topic tronqué
  à 50 chars. Date = aujourd'hui (TZ Paris).

### 6. Suivi posting manuel

Rappeler au user (jusqu'à P11 live) :

> Une fois le post copié-collé et publié, édite le frontmatter du draft :
> - `status: posted`
> - `posted_at: YYYY-MM-DDTHH:MM`
> - `url_posted: <permalink>`

Cela permettra à ContentBot full (P9 après P11) de skipper les drafts
déjà postés et d'analyser l'engagement J+1.

### 7. Notif Discord (optionnel)

Pousser sur `DISCORD_WEBHOOK_OPS_LOGS` si configuré :
« Draft content livré : [<channel>] <topic> · `data/content/drafts/<file>` ».

## Garde-fous (refuser fermement)

- **Génération sans KB** — refuser, expliquer risque ton générique IA.
- **Cross-posting identique** — refuser « le même post pour les 4
  canaux ». Chaque canal exige une formulation propre.
- **Stats inventées** — toute statistique chiffrée doit avoir une source
  réelle. Sinon retirer.
- **FUD vs concurrents** — respect strict de `competitor_compare.md`
  § anti-disparagement.
- **Buzzwords corporate** — « game changer », « disruptif », « innovant »,
  « synergie » → refuser et reformuler.
- **Promotion directe Reddit** sans contexte 9:1 validé.
- **Emoji marketing en cascade** sur Mastodon/Reddit (zéro toléré).
- **CTA agressif** — « Cliquez ici maintenant ! » → refuser.

## Sortie attendue

Fichier `data/content/drafts/YYYY-MM-DD-<channel>-<slug>.md` avec frontmatter
et body conformes à `.claude/skills/content-writer/SKILL.md` § Outputs.

Status initial : `draft`. À passer manuellement à `validated` quand le
fondateur valide pour posting, puis `posted` après publication réelle.

## Test plan (à dérouler en P9-DRAFT closure)

- [ ] `/draft-content linkedin "faux positifs DAST"` → draft généré,
      character_count 1300-2000, kb_sources non vide, fichier écrit.
- [ ] `/draft-content mastodon "OWASP API Top 10 2023"` → draft 300-500 chars,
      pas d'emoji marketing, lien à la fin.
- [ ] `/draft-content reddit "..."` sans validation 9:1 → refus + proposition
      de réponse technique à une question existante.
- [ ] `/draft-content` sans argument → propose (canal, topic) cohérent
      basé sur historique drafts.
- [ ] Vérifier garde-fou : demander « invente une stat » → refus +
      proposition d'alternative.

## Liens

- Skill : `.claude/skills/content-writer/SKILL.md`
- Drafts : `data/content/drafts/`
- KB : `data/knowledge_base/`
- Plan P9 full : `docs/ARGOS_OPS_PLAN.md` § Partie 9
