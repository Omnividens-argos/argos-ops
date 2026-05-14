---
name: content-writer
description: Génère un post pour un canal social donné (LinkedIn / Mastodon / Reddit r/netsec / X) à partir d'un topic + la KB Argos. Mode local-draft only (P9-DRAFT, 2026-05-14) — pas de posting tant que P11 (connecteurs sociaux) n'est pas livré. Utilise ce skill quand le user demande de drafter un post, de préparer du contenu social, ou pendant /draft-content. Anti-générique IA via charge systématique du contexte KB (kb-rag P6).
---

# content-writer

Skill éditorial pour produire des posts social Argos qui :

- **N'ont pas le ton générique IA** (le risque #1 selon `MASTER_PROMPT.md`)
- Sont **factuels et adaptés au canal** (longueur + format + tonalité par
  plateforme, respect règles communautaires)
- S'appuient sur la **KB curée** (`tone_of_voice`, `argos_features`,
  `competitor_compare`, `pricing`, `ICP`, `faq`)
- Sont **rangés dans une queue locale** (`data/content/drafts/`) en
  attendant que P11 (connecteurs LinkedIn/Mastodon/Reddit) soit livré.
  D'ici là, posting **manuel** par le fondateur après validation.

> **Note P9-DRAFT vs P9 full** : ce skill couvre la phase MVP draft-only.
> Quand P11 sera done, ContentBot (P9 full) consommera cette même queue
> et postera automatiquement après agent-juge Tier 1 (P14).

## Canaux supportés et contraintes

| Canal | Longueur | Format | Anti-pattern critique |
|-------|----------|--------|------------------------|
| **LinkedIn** | 1300-2000 chars | Hook 1 ligne → 3-4 paragraphes courts → CTA soft → 3-5 hashtags | Pas de buzzwords corporate (« synergie », « game changer »). Pas d'emoji marketing. |
| **Mastodon** (infosec.exchange) | 300-500 chars | 1-2 paragraphes, ton tech crowd, 2-3 hashtags, lien à la fin | **Bot flag activé** sur le compte (requis par règles instance). Pas de promo directe — partage technique d'abord. |
| **Reddit r/netsec** | 800-2000 mots | Longform technique, jamais de pitch produit direct | **Règle 9:1** : 9 contributions utiles non promo pour 1 mention produit. Ban = perte du canal. Pas de lien sortant en première mention. |
| **X / Twitter** | ≤ 280 chars | 1 idée forte, 1 hashtag max, lien optionnel | Free tier supprimé (D-004) — canal **bas priorité**, ne pas y consacrer d'effort. |

## Inputs

- `topic` — sujet du post (ex : `"faux positifs DAST"`, `"correction
  hebdo SecHunter v2.4"`, `"OWASP API Top 10 review"`)
- `channel` — `linkedin | mastodon | reddit | x`
- `(optionnel) angle` — angle éditorial précis (sinon, l'agent propose 2-3 options)
- `(optionnel) cta` — call-to-action voulu (lien démo, blog post, etc.)

## Outputs

Un fichier markdown dans `data/content/drafts/YYYY-MM-DD-<channel>-<slug>.md`
avec **exactement** cette structure :

```markdown
---
channel: linkedin | mastodon | reddit | x
status: draft | validated | posted | rejected
date_created: YYYY-MM-DD
posted_at: null
topic: "<topic court>"
angle: "<angle retenu>"
character_count: <int — bytes du body uniquement, hors frontmatter>
word_count: <int — pour Reddit longform>
kb_sources: ["pricing.md§Pro Max", "competitor_compare.md§Acunetix", ...]
cta: "<lien ou null>"
url_posted: null  # rempli manuellement par le fondateur après posting
---

<body du post, exactement ce qui sera copié-collé dans le canal>
```

> **Important** : le body est livré **prêt à copier-coller**. Pas de
> markdown LinkedIn (LinkedIn ignore `**bold**`), pas de smart quotes
> bizarres, sauts de ligne respectés.

## Procédure (humain-in-the-loop)

### 1. Validation des inputs

- Si `channel` n'est pas dans `{linkedin, mastodon, reddit, x}` → demander
  lequel.
- Si `topic` est vague (« cybersecurity », « tech ») → demander précision.
- Si `channel=reddit` et c'est le premier post de la session → rappeler
  la règle 9:1 et demander : « Combien de contributions non-promo as-tu
  postées sur r/netsec récemment ? » Si < 9 → refuser et proposer d'écrire
  une réponse technique à une question existante d'abord.

### 2. Chargement contexte KB

Invoquer le skill `kb-rag` (P6) avec `topic` pour récupérer les chunks
KB pertinents (top-5). En complément, charger systématiquement :

- `data/knowledge_base/tone_of_voice.md` — ton + canaux (référence)
- `data/knowledge_base/ICP.md` — qui lit ce canal (Marc / Sarah / Thomas)

Conditionnellement selon le topic :

- mention pricing → `pricing.md`
- comparaison concurrent → `competitor_compare.md`
- feature spécifique → `argos_features.md` + `argos_modules.raw.json`
- objection client → `faq.md`

### 3. Drafting interactif (mode interview court)

Pour chaque post, **proposer** puis **demander validation** :

1. **Angle** — 2-3 propositions d'angle éditorial avec rationale court
   (« angle A traite l'objection X de Marc »).
2. **Hook / 1re ligne** — la phrase qui doit accrocher dans le feed.
   LinkedIn/X : 1 ligne forte ; Mastodon : 1 phrase tech ; Reddit : titre
   du post (≤ 300 chars).
3. **Corps** — adapter à la longueur canal :
   - **LinkedIn** : 3-4 paragraphes max 4 lignes chacun, séparés par
     ligne vide. Une idée par paragraphe. Pas de listes à puces sauf
     si vraiment utile (LinkedIn casse souvent le formatting).
   - **Mastodon** : 1-2 paragraphes denses, tech vocabulary OK (audience
     l'attend).
   - **Reddit** : intro problème → analyse technique → conclusion
     actionnable. Citations de sources. Markdown standard supporté.
   - **X** : 1 phrase + 1 lien.
4. **CTA** — soft, matché à l'intent du canal :
   - LinkedIn : « Démo ? » ou lien vers `omnividens.fr/blog/<post>`
   - Mastodon : lien vers feature page ou blog, pas vers démo
   - Reddit : **aucun CTA produit** dans 9 posts sur 10 ; 10e post = lien
     dans une réponse en commentaire, jamais dans le post initial
   - X : lien permalink
5. **Hashtags** — appliquer le quota par canal (cf. tableau).

### 4. Validation finale + écriture

- Afficher le post complet en preview, **compter les caractères**.
- Vérifier la contrainte longueur du canal — si dépassée, **refuser
  d'écrire** et proposer de raccourcir d'abord.
- Demander : « OK pour écrire dans `data/content/drafts/<filename>.md` ? »
- Si oui, écrire avec le `Write` tool. Slug = kebab-case du topic tronqué
  à 50 chars.

### 5. Notif Discord (optionnel)

Pousser sur `DISCORD_WEBHOOK_OPS_LOGS` si configuré :
« Draft content livré : [<channel>] <topic court> · `data/content/drafts/<file>` ».
Pas bloquant.

## Anti-patterns à refuser

- **Génération sans KB** — refuser, expliquer le risque ton générique IA.
- **Stats inventées** — toute statistique chiffrée (« 87 % des RSSI… »)
  doit venir d'une source réelle. Sinon retirer ou demander source au user.
- **FUD vs concurrents** — respect strict de `competitor_compare.md`
  § anti-disparagement. Reformuler en factuel.
- **Buzzwords corporate** — « game changer », « disruptif », « innovant »,
  « synergie » → refuser et reformuler.
- **Emoji marketing en cascade** — 🚀🔥💯 = pas notre tone. 1 emoji
  technique acceptable côté LinkedIn si pertinent (📊 sur un benchmark).
  Pas d'emoji sur Mastodon/Reddit.
- **CTA agressif** — « Cliquez ici maintenant ! », « Ne ratez pas ! » →
  refuser.
- **Promotion directe Reddit** sans contexte 9:1 validé.
- **Plus de 5 hashtags LinkedIn** — l'algo punit (cf. tone_of_voice).
- **Cross-posting identique** — chaque canal doit avoir une formulation
  adaptée. Refuser « génère le même post pour les 4 canaux ».

## Tests / validation

Pas de tests Python (skill éditorial pur, même pattern que
`seo-brief-writer`). Critères qualité par post :

- ✅ Frontmatter YAML valide et complet
- ✅ `character_count` (LinkedIn/Mastodon/X) ou `word_count` (Reddit)
      dans les bornes du canal
- ✅ Au moins 1 `kb_sources` listée (preuve que la KB a été consultée)
- ✅ Hook accroche sur la 1re ligne (test : couper après la 1re ligne,
      ça donne envie de lire ?)
- ✅ Zéro buzzword corporate
- ✅ Zéro stat sans source

## Workflow attendu (boucle hebdo)

1. Fondateur lance `/draft-content <channel> <topic>` 2-5×/semaine
2. Skill produit un draft validé dans `data/content/drafts/`
3. Fondateur copie-colle manuellement dans le canal (P11 pas encore live)
4. Une fois posté, fondateur édite le frontmatter :
   `status: posted` + `posted_at: YYYY-MM-DDTHH:MM` + `url_posted: <permalink>`
5. **Quand P11 sera done** : ContentBot (agent Python) lira cette queue,
   poussera automatiquement les drafts `status: validated` via les
   connecteurs, et la boucle deviendra autonome (avec ClaudeJudge P14
   en supervision).

## Liens

- Slash command `/draft-content` : `.claude/commands/draft-content.md`
- Drafts produits : `data/content/drafts/`
- KB consommée : `data/knowledge_base/` (6 fichiers)
- Skill réutilisé : `kb-rag` (P6)
- Skill cousin : `seo-brief-writer` (P10-MVP) — pour les briefs blog longform
- Plan P9 full : `docs/ARGOS_OPS_PLAN.md` § Partie 9
