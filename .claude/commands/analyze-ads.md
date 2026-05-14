---
description: Analyse un CSV export Google Ads / LinkedIn / Meta et produit 3-5 recommandations chiffrées (pause / drop keyword / scale / nouvelle créa) dans `data/ads/recommendations/`. Mode shadow uniquement — aucune action en plateforme. Garde-fous breakers P15 (`ad_spend_runaway`).
---

# /analyze-ads

Slash command interactif pour piloter les campagnes Argos en mode shadow
(P12, D-017). Lit un CSV manuel, calcule les métriques, propose des actions
chiffrées. Le fondateur applique manuellement.

## Usage

- `/analyze-ads <csv_path>` — analyse le CSV donné
- `/analyze-ads` — propose le dernier CSV disponible dans
  `data/ads/campaigns/` ou demande au fondateur d'exporter

## Workflow

### 1. Lecture + validation CSV

- Si `csv_path` n'existe pas → demander au fondateur d'exporter :
  - **Google Ads** : Rapports → Modèles prédéfinis → « Campaign
    performance » → période 14 j → Télécharger CSV → poser dans
    `data/ads/campaigns/YYYY-MM-DD-google_search.csv`
  - **LinkedIn** : Campaign Manager → Campaigns → Export → idem
  - **Meta** : Ads Manager → Reports → Export CSV → idem
- Vérifier colonnes minimales : `Campaign`, `Impressions`, `Clicks`,
  `Cost`, `Conversions`. Si manquantes → ajouter au rapport plateforme.
- Inférer `platform` depuis les colonnes (ex : `Quality Score` → Google ;
  `Avg CPM` → LinkedIn/Meta).

### 2. Confirmation paramètres

Demander au fondateur :

- **CPA cible** (défaut 80 € pour démo BtoB Argos selon LTV Pro Max)
- **Période d'analyse** (défaut 14 j — assez pour signaux fiables, pas
  trop pour rester réactif)
- **Filtre campagne** (optionnel — si le fondateur veut zoomer)

### 3. Calcul métriques + comparaisons

- Par campagne : CTR, CPC, CPA, conv rate
- Global : agrégé toutes campagnes
- Si CSV semaine précédente dispo dans `data/ads/campaigns/` → delta %
  sur chaque métrique vs S-1
- Flag chaque campagne : `bleeding` (CPA > 2× cible), `marginal`
  (cible ≤ CPA ≤ 2× cible), `healthy` (CPA < cible ET CTR ≥ benchmark)

### 4. Génération recommandations (max 5)

Prioriser par impact € :

1. **PAUSE** campagne `bleeding` ≥ 2 semaines → -X €/semaine
2. **DROP keyword** (Google) ≥ 100 € spend, 0 conv, ≥ 2 semaines
3. **TEST créa nouvelle** (`CTR < benchmark` mais conv rate OK) →
   invite à lancer `/draft-ad`
4. **SCALE +X %** campagne `healthy` ≥ 6 semaines, budget non saturé
5. **DIAGNOSTIC LP** (CTR OK mais conv rate < 1 %) → LP ou ciblage cassé

**Max 5** — au-delà, le fondateur sature. Le reste va dans
« Notes complémentaires ».

### 5. Audit agent-juge (P14) — optionnel mais recommandé

Invoquer `claude-judge` avec : `draft = bloc recommendations` +
`channel = 'blog'` (analyse interne) + `agent_name = 'AdBot'`.

Si verdict `killed` ou `queued` à cause de claims chiffrés non sourcés
(ex : « benchmark CTR secteur 2.1 % » sans source) → corriger en
flageant « source TBD » avant écriture.

### 6. Évaluation breaker `ad_spend_runaway` (P15)

Compute `daily_spend` (= total cost / window_days). Si
`daily_spend > 1.5 × cpa_target × daily_conv_target` :

```python
from argos_ops.breakers import trip_with_notification
await trip_with_notification(
    "ad_spend_runaway",
    reason=f"Spend {daily_spend:.0f}€/j > 1.5x cible ({cpa_target}€)",
    severity="critical",
)
```

Mentionner dans la reco que le breaker a été tripé (le fondateur le verra
aussi dans Discord + dashboard P16).

### 7. Écriture + validation

- Preview le markdown complet (snapshot global + N recommandations +
  garde-fous breakers).
- Demander : « OK pour écrire dans
  `data/ads/recommendations/YYYY-MM-DD-<platform>-<scope>.md` ? »
- Si oui : `Write` tool + renommer le CSV source dans
  `data/ads/campaigns/YYYY-MM-DD-<platform>.csv` (servira de base
  comparaison S-1 la semaine prochaine).

### 8. Notif Discord

Pousser sur `DISCORD_WEBHOOK_OPS_LOGS` :

```
[AdBot shadow] Reco générée : <N> actions
Top impact : <€>/semaine via <action courte>
Détails : data/ads/recommendations/<file>
```

Si breaker `ad_spend_runaway` tripped → notif séparée critique sur
`DISCORD_WEBHOOK_ALERTS`.

## Garde-fous (refuser fermement)

- **Recommandations vagues** — « augmenter le budget » sans % chiffré
  + impact estimé en € → refus.
- **Stat marché inventée** — refuser « benchmark CTR 2.1 % » sans source.
  Utiliser benchmark interne d'autres campagnes Argos ou flag « source TBD ».
- **Plus de 5 recommandations** — refuser, prioriser. Backlog → notes
  complémentaires.
- **Recommandation appliquée par l'agent** — interdit en mode shadow.
  Le fondateur applique manuellement.
- **CPA target non précisé** — refuser, demander la valeur.

## Sortie attendue

Fichier `data/ads/recommendations/YYYY-MM-DD-<platform>-<scope>.md` au
format défini dans `.claude/skills/ads-optimizer/SKILL.md` § Outputs.

Status initial : `draft`. Le fondateur le passe à `partially_applied`
ou `fully_applied` manuellement après avoir appliqué les actions en
plateforme.

## Test plan (à dérouler en P12 closure)

- [ ] `/analyze-ads data/ads/campaigns/2026-05-14-google_search.csv` →
      recommandations chiffrées (€/semaine), CPA calculé, breaker non
      tripé
- [ ] CPA target non précisé → refus + demande de valeur
- [ ] CSV sans colonne Conversions → refus + demande de ré-export
- [ ] Stat « benchmark secteur 2.1 % » → flag « source TBD » avant écriture
- [ ] Daily spend > 1.5× cible → breaker `ad_spend_runaway` tripé +
      notif Discord visible

## Liens

- Skill : `.claude/skills/ads-optimizer/SKILL.md`
- Skill cousin : `.claude/skills/ads-creative-writer/SKILL.md`
- Slash command cousin : `/draft-ad` (génère 3 variantes pour tester)
- Breakers : `argos_ops/breakers.py` (P15) — `ad_spend_runaway`
- Données : `data/ads/campaigns/` (CSV historiques) ·
  `data/ads/recommendations/` (output) · `data/ads/drafts/`
- Plan P12 full : `docs/ARGOS_OPS_PLAN.md` § Partie 12
