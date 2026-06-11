---
description: Drafte une séquence outbound 5-touches pour 1 lead (P13.A shadow). Humain-in-the-loop — invoque lead-enricher + outbound-personalizer + claude-judge sur chaque touche. Mode local-draft only, aucun envoi tant que P13.B live mode n'est pas activé.
---

# /draft-outbound `<slug>`

Slash interactif pour remplir le **body** de chaque touche d'une séquence
scaffold par `OutboundBot`. Humain pilote pour garantir qualité éditoriale
et conformité (intérêt légitime BtoB, opt-out, AI Act).

## Usage

```
/draft-outbound marc-dupont-acme-fr
```

Le slug est celui produit par `OutboundBot` (cf. `data/outbound/sequences/<slug>/`).

## Préconditions

- La séquence existe : `data/outbound/sequences/<slug>/meta.yaml` présent
- `OUTBOUND_UNSUBSCRIBE_SECRET` configuré
- KB Argos seedée (kb-rag disponible pour contexte produit)

## Workflow

### 1. Charger l'état

```python
from argos_ops.outbound import load_sequence_state

state = load_sequence_state("<slug>")
```

Affiche au user :
- `full_name`, `domain`, `sequence_status`
- Liste des 5 touches avec leur status courant (`scaffold` / `drafted` / etc.)
- Si `enriched_path` existe déjà et fichier présent → afficher persona,
  email_guesses, BANT pour contexte. Sinon → étape 2.

### 2. Enrichir (si pas déjà fait)

Si `data/outbound/enriched/<slug>.md` n'existe pas :

> Invoque le skill `lead-enricher` avec :
> ```yaml
> full_name: "<state.full_name>"
> domain: "<state.domain>"
> title_hint: <si présent dans meta.yaml>
> linkedin_url: <si présent dans meta.yaml>
> ```
>
> Le skill produit le fichier enriched avec frontmatter complet (BANT,
> persona, signaux ICP, email_guesses).

**Si BANT < 40** ou **disqualifiers présents** (email perso, persona hors
ICP, etc.) → demander à l'humain : « Lead disqualifié — passer en `dnq` ?
Sinon, justifie pourquoi on garde. »

### 3. Personnaliser (la ligne 1)

Si frontmatter `personalizer.line_1` absent dans enriched :

> Invoque le skill `outbound-personalizer` sur `data/outbound/enriched/<slug>.md`
> avec `sequence_step=1` et angle suggéré par persona.

**Garde-fou anti-fake-perso** : si le skill refuse (pas de source publique
précise trouvée), demander à l'humain de fournir une URL/référence ou de
passer le lead en `dnq`.

### 4. Drafter chaque touche (1 à 5)

Pour chaque touche `step ∈ [1..5]` dont `status == "scaffold"` :

1. Charger le template par step (cf. `argos_ops/outbound/models.py` —
   `TouchStep` docstring) :
   - **DISCOVERY (D+0)** : opener (= personalizer.line_1) + 1 paragraphe
     value prop court + **1 question simple** (pas un pitch)
   - **VALUE (D+3)** : drop d'un asset utile (blog post Argos, mini-démo,
     OWASP cheat sheet). Pas de pitch produit direct.
   - **CASE (D+7)** : étude de cas concrète avec chiffres (« sur N
     scans, M FP identifiés vs Acunetix »). Toujours sourcer la KB.
   - **PROOF (D+14)** : témoignage client OU feature spécifique liée
     au signal ICP du lead (ex : "Marc" + CI/CD → mention oracle).
   - **BREAKUP (D+30)** : break-up email **court** (3-5 lignes) — « je
     vous laisse tranquille, dernière fois ». Pas de relance après.

2. Charger le contexte KB via `kb-rag` :
   - Toujours : `tone_of_voice.md`, `ICP.md`
   - Conditionnellement : `pricing.md` (si CASE/PROOF), `competitor_compare.md`
     (si lead vient d'Acunetix/Detectify), `argos_features.md` (si feature
     spécifique).

   Charger aussi la **mémoire de flotte** :
   `uv run python scripts/fleet_memory_in.py OutboundBot` — signaux leads
   inbound (EmailBot), objections récurrentes, heuristiques LeadEnricher.
   Une objection connue = l'adresser proactivement dans la touche CASE.

3. Proposer **subject + body** à l'humain. Demander validation.

4. **Audit `claude-judge` obligatoire AVANT écriture** :
   ```yaml
   channel: email
   agent_name: OutboundBot
   draft: "<subject + body>"
   original_query: "<topic de la touche>"
   rag_chunks: "<chunks chargés>"
   ```
   - `verdict='killed'` → refuser d'écrire, demander reformulation
   - `verdict='queued'` → écrire avec `status='drafted'` mais lister les
     issues judge dans le frontmatter
   - `verdict='auto_send'` → écrire avec `status='drafted'`, prêt pour
     validation finale humaine

5. **Footer obligatoire** sur chaque touche — généré via :
   ```python
   from argos_ops.outbound.templates import build_footer
   from argos_ops.config import get_settings

   s = get_settings()
   footer = build_footer(
       email="<email final du lead>",
       secret=s.outbound_unsubscribe_secret.get_secret_value(),
       tagline=s.email_signature_tagline,
       site_url=s.email_signature_site_url,
       ai_disclosure=s.email_signature_ai_disclosure,
   )
   ```
   Le footer contient : tagline + URL site + AI disclosure + mention RGPD
   intérêt légitime + lien opt-out 1-clic HMAC.

6. Écrire dans `data/outbound/sequences/<slug>/touch_<step>.md` :
   ```markdown
   ---
   step: <N>
   step_label: "<label>"
   scheduled_date: <YYYY-MM-DD>
   status: drafted
   subject: "<subject>"
   judge_score: <0-100>
   judge_verdict: auto_send | queued
   sent_at: null
   ---

   <body>

   <footer>
   ```

7. Patcher `meta.yaml` : touche `status: drafted`, `judge_score`, `judge_verdict`.

### 5. Validation finale humaine

Quand toutes les touches sont `drafted` :

- Afficher la preview de chaque touche
- Demander : « OK pour passer la séquence en `sequence_status: drafting` ?
  Touches en mode validated seront envoyées par P13.B live mode (quand
  domaine secondaire + `OUTBOUND_LIVE_MODE=true`). »

- Si oui : patcher `meta.yaml` (`sequence_status: drafting`)

### 6. Notif Discord (optionnel)

```
Sequence outbound draftée : <slug> · 5 touches · judge avg <score>/100 · `data/outbound/sequences/<slug>/`
```

## Garde-fous (refuser fermement)

- **Email perso détecté** (`@gmail.com`, `@yahoo.fr`, `@hotmail.com`,
  `@orange.fr`, etc.) → refuser, passer le lead en `dnq` (RGPD intérêt
  légitime BtoB ne couvre PAS les emails perso)
- **Lead BANT < 40 sans justification** → refuser
- **Footer absent ou opt-out non signé** → refuser (compliance hard)
- **Subject racoleur** (« URGENT », « LAST CHANCE », « 50% OFF ») →
  refuser, reformuler
- **CTA agressif** dans touche 1-2 → refuser (l'opener ne vend pas, il établit
  la légitimité)
- **Faux compliment** (« j'ai vu votre profil intéressant », « bravo pour
  vos belles réalisations ») → refuser (anti-fake-perso strict)
- **Cross-touch identique** — refuser si touche 2 répète touche 1 (chaque
  touche apporte un angle nouveau)

## Test plan (à dérouler en P13.A closure)

- [ ] `/draft-outbound <slug-inexistant>` → erreur claire « séquence
      inconnue »
- [ ] `/draft-outbound <slug>` sans enriched → enriched généré en step 2
- [ ] `/draft-outbound <slug>` avec BANT 25 → refus + suggestion `dnq`
- [ ] Touche 1 avec stat inventée → judge `killed` → refus écriture
- [ ] Email perso `@gmail.com` détecté → disqualification immédiate
- [ ] Footer généré contient bien l'opt-out URL HMAC vérifiable

## Liens

- Skills : `.claude/skills/lead-enricher/`, `.claude/skills/outbound-personalizer/`,
  `.claude/skills/claude-judge/`
- Module Python : `argos_ops/outbound/` (templates + sequence IO)
- Agent : `argos_ops/agents/outbound_bot.py`
- Workflow complet : `data/outbound/README.md`
- Plan P13 : `docs/ARGOS_OPS_PLAN.md` § Partie 13
