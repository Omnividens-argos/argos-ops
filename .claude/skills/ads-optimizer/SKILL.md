---
name: ads-optimizer
description: Analyse les perfs de campagnes Ads (CSV export depuis Google Ads / LinkedIn Campaign Manager / Meta Ads Manager) et propose 3-5 actions chiffrées (pause / budget +/- / nouvelle créa). Mode shadow uniquement (P12, 2026-05-14) — recommandations posées dans `data/ads/recommendations/`, jamais appliquées en API tant que le fondateur n'a pas confirmé budget + credentials. Anti-FUD interne (« CPA cible » sourcé, pas de seuil arbitraire). Garde-fous P15 : breaker `ad_spend_runaway` si dépense > 1.5× budget cible / 24h.
---

# ads-optimizer

Skill analytique pour piloter les campagnes Argos (Google / LinkedIn / Meta) :

- **Lit** un export CSV/JSON manuel (le fondateur exporte depuis l'UI plateforme
  une fois par semaine en attendant l'intégration API)
- **Calcule** les métriques canoniques (CTR, CPC, CPA, ROAS, conversion rate)
  + delta vs semaine précédente
- **Propose** 3-5 actions chiffrées + rationale + niveau de risque
- **Ne touche à rien** en plateforme — toute action reste manuelle tant qu'on
  n'est pas en live mode (P12.B, futur)

> **Mode shadow P12 2026-05-14** : output = markdown dans
> `data/ads/recommendations/`. Le fondateur applique manuellement
> les actions qu'il valide.

## Vocabulaire canonique

| Terme | Définition stricte | Pourquoi c'est précis |
|---|---|---|
| **CTR** | `clicks / impressions` × 100, en % | Mesure attrait créa pour l'audience servie |
| **CPC** | `cost / clicks` | Coût d'un click, à comparer au CPC marché secteur |
| **CPA** | `cost / conversions` | Coût d'une conversion (demo bookée, lead qualifié) |
| **Conv rate** | `conversions / clicks` × 100 | Qualité ciblage + LP — si CTR bon mais conv rate faible, la LP ou le ciblage est cassé |
| **ROAS** | `revenue / cost` | Vrai ROI — nécessite que Stripe + UTM soient bien câblés (P7 FinanceBot + P11 social UTMs) |
| **Quality Score (Google)** | 1-10, propre à Google | Pondère le CPC, dépend de la LP + CTR + pertinence keyword |

## Inputs

- `csv_path` — chemin du CSV exporté (Google Ads = report « Campaign performance »
  / LinkedIn = Campaign Manager export / Meta = Ads Manager export)
- `(optionnel) platform` — inféré depuis colonnes CSV si pas fourni
- `(optionnel) campaign_filter` — filtre par nom de campagne (substring)
- `(optionnel) cpa_target_eur` — CPA cible en euros pour décider pause/scale
  (cf. ICP plan_value_eur) ; défaut 80 € pour démo BtoB Argos

## Outputs

Un fichier markdown dans `data/ads/recommendations/YYYY-MM-DD-<platform>-<scope>.md` :

```markdown
---
platform: google_search | linkedin_sponsored | meta_image
date_generated: YYYY-MM-DD
window: "<période analysée — ex 7d ou 14d>"
cpa_target_eur: 80
campaigns_analyzed: 5
total_spend_eur: 412.50
total_conversions: 4
overall_cpa_eur: 103.13
status: draft | validated | partially_applied | fully_applied
---

## Snapshot global

- Spend : <€>  · CTR : <%> · CPC : <€> · Conv : <int> · CPA : <€> · vs S-1 : <±%>
- Verdict global : `healthy` | `marginal` | `bleeding`

## Recommandations (par priorité)

### 1. **PAUSE** campagne « <nom> » 🔴 high-impact
- **Pourquoi** : CPA 234 € vs cible 80 € sur 14 j, conv rate 0.4 % (<1 % seuil)
- **Action concrète** : Google Ads UI → campagne X → status = Paused
- **Impact attendu** : -120 €/semaine de spend non productif
- **Réversible** : oui, 1 click

### 2. **DROP** keyword « <kw> » 🟡 medium-impact
- **Pourquoi** : 320 € spend, 0 conv, 4 weeks
- **Action concrète** : ad group Y → negative match → ajouter `[<kw>]`
- **Impact attendu** : -25 €/semaine
- **Réversible** : oui

### 3. **TEST** nouvelle créa via `ads-creative-writer` 🟢 exploration
- **Pourquoi** : CTR campagne Z = 0.8 % (< benchmark 2.1 % secteur SaaS BtoB)
- **Action concrète** : `/draft-ad google_search leads marc <angle>`
- **Impact attendu** : si CTR remonte à 2 %, -40 €/semaine sur même volume conv
- **Réversible** : oui (split-test 14j)

### 4. **SCALE +20 %** campagne « <nom> » 🟢 high-confidence
- **Pourquoi** : CPA 62 € (sous cible 80 €), volume stable 6+ semaines, ROAS 4.2x
- **Action concrète** : budget journalier +20 % (de 50 → 60 €)
- **Impact attendu** : +1-2 conv/semaine
- **Réversible** : oui ; **garde-fou** : breaker `ad_spend_runaway` trip si
  spend > 1.5× budget cible/24h

### 5. ...

## Garde-fous breakers (P15)

- `ad_spend_runaway` : trip auto si dépense > 1.5× budget cible / 24h →
  pause toutes campagnes + notif Discord. Cf. `argos_ops/breakers.py` (sera
  câblé par AdBot agent Python en P12.B, futur).

## Notes complémentaires

<bullets : changements UI plateforme à noter, problèmes de tracking,
suggestions backlog>
```

## Procédure (humain-in-the-loop)

### 1. Lecture + validation CSV

- Si fichier n'existe pas → demander au fondateur de l'exporter avec
  procédure type :
  - Google Ads : Rapports → Modèles prédéfinis → « Campaign performance »
    → période 14 j → Télécharger CSV
  - LinkedIn : Campaign Manager → Campaigns → Export
  - Meta : Ads Manager → Reports → Export CSV
- Vérifier les colonnes minimales :
  - Toutes : `Campaign`, `Impressions`, `Clicks`, `Cost`, `Conversions`
  - Recommandé : `CTR`, `Avg CPC`, `Quality Score` (Google),
    `Conversion rate`, `Cost per conv`
- Si colonnes manquantes → demander au fondateur d'ajouter au rapport.

### 2. Calcul métriques + comparaisons

- Compute par campagne : CTR, CPC, CPA, conv rate
- Compute global (agrégé toutes campagnes)
- Si CSV semaine précédente disponible (`data/ads/campaigns/YYYY-MM-DD-*.csv`),
  calculer delta % sur chaque métrique
- Flag `bleeding` toute campagne avec `CPA > 2 × cpa_target` OU `CTR < 0.5 %`
- Flag `marginal` toute campagne avec `cpa_target ≤ CPA ≤ 2 × cpa_target`
- Flag `healthy` toute campagne avec `CPA < cpa_target` ET `CTR ≥ benchmark`

### 3. Génération recommandations

Prioriser par impact € :
1. **Pause d'urgence** (`bleeding` ≥ 2 semaines)
2. **Drop keyword** (≥ 100 € spend, 0 conv, ≥ 2 semaines) — Google uniquement
3. **Test créa nouvelle** (`CTR < benchmark secteur` mais conv rate OK)
4. **Scale +X %** (`healthy` ≥ 6 semaines, budget non saturé)
5. **Diagnostic LP** (CTR OK mais conv rate < 1 % → la LP ou le ciblage cassé)

**Maximum 5 recommandations** par run — au-delà, le fondateur sature et
n'applique rien.

### 4. Audit agent-juge (P14) — optionnel mais recommandé

Invoque `claude-judge` avec : `draft = bloc recommendations` +
`original_query = csv_summary` + `channel = 'blog'` (analyse interne, pas
public) + `agent_name = 'AdBot'`. Objectif : flag les recommandations qui
font des claims chiffrés non sourcés (ex : « benchmark secteur 2.1 % CTR »
sans source).

### 5. Écriture + validation

- Preview le markdown complet.
- Demander : « OK pour écrire dans `data/ads/recommendations/<filename>.md` ? »
- Si oui, écrire.
- Renommer le CSV source vers `data/ads/campaigns/YYYY-MM-DD-<platform>.csv`
  pour servir de base de comparaison la semaine suivante.

### 6. Notif Discord

Pousser sur `DISCORD_WEBHOOK_OPS_LOGS` :
```
[AdBot shadow] Reco générée : <N> actions, top impact = <€>/semaine
Détails : data/ads/recommendations/<file>
```

Si **breaker `ad_spend_runaway` doit trip** (dépense > 1.5× budget cible / 24h)
→ appeler `argos_ops.breakers.trip_with_notification('ad_spend_runaway', ...)`
**même en mode shadow** (le breaker bloquera tout AdBot live mode futur).

## Anti-patterns à refuser

- **Recommandations vagues** — refuser « augmenter le budget » sans
  pourcentage chiffré et impact estimé.
- **Stat marché inventée** — refuser « benchmark CTR secteur 2.1 % » si
  on n'a pas la source. Mieux : utiliser benchmark interne d'autres
  campagnes Argos ou flagger « source TBD ».
- **Plus de 5 recommandations** — refuser, prioriser. Backlog le reste
  dans la section « Notes complémentaires ».
- **Recommandation appliquée par l'agent** — interdit en mode shadow.
  Le fondateur applique manuellement. (Quand on passera en live mode
  P12.B, un AdBot Python wrappera Google Ads API avec les hard caps
  du plan § 12.1.)
- **CPA target non précisé** — refuser, demander la valeur (un CPA
  raisonnable BtoB démo Argos = 60-100 € selon LTV Pro Max).

## Tests / validation

Pas de tests Python (skill analytique pur, pattern P9-DRAFT / P10-MVP).
Critères qualité par run :

- ✅ Toutes les métriques calculées présentes (CTR, CPC, CPA, conv rate)
- ✅ Chaque recommandation = action concrète + impact € chiffré + réversibilité
- ✅ Aucune stat de marché sans source ou flag « source TBD »
- ✅ Breaker `ad_spend_runaway` évalué (même si pas tripé, doit être mentionné)

## Liens

- Slash command `/analyze-ads` : `.claude/commands/analyze-ads.md`
- Skill cousin : `ads-creative-writer` (génère 3 variantes pour tester)
- Skill réutilisé : `claude-judge` (P14, optionnel)
- Breakers : `argos_ops/breakers.py` (P15) — `ad_spend_runaway`
- Plan P12 full : `docs/ARGOS_OPS_PLAN.md` § Partie 12
- Données : `data/ads/campaigns/` (CSV historiques) ·
  `data/ads/recommendations/` (output) · `data/ads/drafts/` (créas de
  `ads-creative-writer`)
