---
name: email-classifier
description: Classifie un email reçu en lead_chaud / question_tech / sav / spam / autre, à partir du sujet et du corps. Utilise ce skill quand le user demande de trier la boîte mail Argos, de prioriser les réponses, ou pendant /check-emails pour orienter le drafting.
---

# email-classifier

Skill **inline Claude** (D-017 — pas d'API LLM tierce). Classifie un email
reçu sur `contact@omnividens.fr` en une catégorie canonique pour orienter
le drafting et la priorisation.

## Catégories canoniques

| Catégorie | Description | Action recommandée |
|---|---|---|
| `lead_chaud` | Demande de démo, pricing, achat, RFP, "rappelez-moi" | Drafter réponse en < 4 h, proposer call ou trial |
| `question_tech` | Question sur fonctionnalités, scope, intégration CI/CD, compatibilité | Drafter réponse RAG sur KB (Argos features, FAQ) |
| `sav` | Bug report, support sur scan en cours, accès compte, facturation | Créer ticket, escalade Tier 2 si bloquant |
| `spam` | Outbound generic, "do you accept guest posts", crypto/SEO snake oil | Marquer lu, ne pas répondre, optionnellement bloquer expéditeur |
| `partenariat` | Proposition de partenariat, intégration, revente | Réponse polie + tag, décision asynchrone |
| `recrutement` | Candidature spontanée, démarchage commercial RH | Réponse polie standard, archiver |
| `presse` | Journaliste, interview, étude de marché | Drafter avec ton porte-parole, escalade fondateur |
| `autre` | Cas non classables (à examiner humain) | Pas d'auto-réponse, escalade |

## Inputs

```python
{
  "subject": str,
  "body_text": str,            # texte brut, déjà nettoyé du HTML
  "from_email": str,
  "from_domain": str | None,   # extract_domain(from_email)
}
```

## Output attendu

```json
{
  "category": "lead_chaud",
  "confidence": 0.85,
  "rationale": "Mention explicite de 'demander une démo' + signature CISO d'une PME 200 pers",
  "suggested_priority": "P1",
  "suggested_response_skeleton": "Remercier, proposer 2 créneaux call cette semaine, joindre lien démo Argos"
}
```

`confidence` ∈ [0, 1]. Si `< 0.6`, retourner `category="autre"` et flagger
pour examen humain. `suggested_priority` ∈ `{P0, P1, P2, P3}` selon urgence.

## Heuristiques (pour calibrer le LLM avant prompt)

### `lead_chaud` (signaux forts)
- "démo", "demo", "trial", "essai", "rappelez-moi", "prix", "pricing", "tarif"
- "RFP", "appel d'offres", "RFQ", "RFI"
- Domaine entreprise vu pour la première fois + signature avec titre
  ("CISO", "RSSI", "Head of Security", "Security Lead", "DPO")

### `question_tech`
- "comment", "supportez-vous", "scan", "intégration", "API", "SAML",
  "compatible", "GitLab", "GitHub", "AWS"
- Souvent provient d'un client existant ou d'un trial actif

### `sav`
- "ne marche pas", "erreur", "404", "500", "stuck", "bloqué", "facture",
  "remboursement", "annuler abonnement", "downgrade"

### `spam`
- "guest post", "SEO", "ranking", "crypto", "investment", "loan"
- Adresses gmail/outlook avec nom générique, signature absente
- Domaine dans liste noire (à maintenir manuellement)

### `partenariat`
- "partenariat", "partnership", "intégration revendeur", "white-label"

### `recrutement`
- "CV", "candidature", "rejoindre", "recrutement", "RH", "talent"
- Cabinets de recrutement reconnus à reconnaître (à maintenir)

## Garde-fous

- **Ne jamais inventer** de catégorie hors de la liste canonique
- **Pas de classification politique** : si l'email mentionne politique,
  religion, sport — ne pas commenter, classifier le contenu pertinent
- Si le corps est manifestement vide ou < 30 caractères, retourner
  `category="autre"`, `confidence=0.0`
- Si l'expéditeur est `is_noreply()` (cf. `zimbra-ops`), ce skill n'est PAS
  invoqué — l'email est juste loggé puis ignoré

### Override AI Act § 5.2 — « Réponse humaine SVP »

Conformément à l'AI Act (article 13) et à notre engagement public
[`data/legal/ai-disclosure.md`](../../data/legal/ai-disclosure.md) § 5.2,
**tout email dont le sujet OU les 200 premiers caractères contiennent**
l'une des expressions suivantes (matching **case-insensitive** sur le
texte normalisé sans accents) **doit être classé** :

- `category = "autre"`
- `confidence = 1.0`
- `suggested_priority = "P1"`
- `rationale = "AI Act § 5.2 — réponse humaine demandée explicitement"`
- `suggested_response_skeleton = "PAS DE DRAFT IA. Escalade Tier 2 (file fondateur), réponse humaine sous 24 h ouvrées."`

Expressions déclencheuses (liste exhaustive, mise à jour si on observe
des variantes en prod) :

- `"réponse humaine"` / `"reponse humaine"`
- `"un humain svp"` / `"un humain s'il vous plaît"` / `"un humain s'il vous plait"`
- `"pas de bot"` / `"pas de chatbot"` / `"pas d'ia"` / `"pas d'iA"`
- `"human reply"` / `"human please"` / `"talk to a human"`
- `"no bot"` / `"no AI"`

Cet override **bypasse** toutes les autres heuristiques. Il garantit
qu'un user qui exerce son droit AI Act art. 13/14 voit son message
quitter le pipeline IA immédiatement. Le check fait partie du contrat
de conformité — ne pas le retirer sans révision juridique.

## Évolution prévue

- **Calibration mensuelle** : tous les 30 emails classifiés, l'opérateur
  audite 5 et corrige les erreurs. Les corrections sont stockées dans
  `data/email_classifier_corrections.jsonl` pour fine-tuning de prompts
- **P14 agent-juge** : la classification deviendra un input du juge pour
  décider si on auto-envoie ou on garde en humain-validation
