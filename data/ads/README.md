# `data/ads/` — pipeline ads shadow mode (P12)

Sous-arborescences :

- [`drafts/`](drafts/) — sortie de `/draft-ad` : 3 variantes A/B/C par
  fichier markdown, prêtes à copier-coller en plateforme
- [`campaigns/`](campaigns/) — CSV historiques exportés manuellement
  depuis Google Ads / LinkedIn Campaign Manager / Meta Ads Manager,
  servent de base de comparaison S vs S-1
- [`recommendations/`](recommendations/) — sortie de `/analyze-ads` :
  3-5 actions chiffrées par fichier markdown, avec impact € estimé

## Mode shadow (actif tant que P12.B live mode n'est pas livré)

1. **Drafting** : `/draft-ad <platform> <objective> <persona>` génère
   3 variantes → `data/ads/drafts/YYYY-MM-DD-<platform>-<slug>.md`
2. **Validation** : le fondateur relit, passe `status: draft` →
   `status: validated`
3. **Publication manuelle** : copie-colle dans la plateforme (Google Ads
   Editor / LinkedIn Campaign Manager / Meta Ads Manager). Édite le
   frontmatter : `status: live` + `posted_at` + `posted_campaign_id`
4. **Mesure** : 1× par semaine, exporte le CSV de perf →
   `data/ads/campaigns/YYYY-MM-DD-<platform>.csv`
5. **Itération** : `/analyze-ads <csv_path>` produit des recommandations
   → `data/ads/recommendations/YYYY-MM-DD-<platform>-<scope>.md`
6. Le fondateur applique manuellement les recos qu'il valide en
   plateforme, édite le frontmatter de la reco
   (`partially_applied` ou `fully_applied`)

## Mode live (futur P12.B — quand budget pub actif + credentials disponibles)

Un agent Python `argos_ops/agents/ad_bot.py` :

1. Pull perf via API Google Ads / LinkedIn Marketing API / Meta Marketing API
2. Applique les actions auto-validées par `claude-judge` (verdict
   `auto_send`) **avec hard caps** :
   - Pause auto si CPA > 2× cible sur 24 h
   - Pas de hausse budget journalier > +10 %/jour
   - Alerte si dépense quotidienne > 1.5× budget cible
3. Breaker `ad_spend_runaway` (P15) kill toutes les campagnes si dépense
   > 1.5× budget cible / 24h
4. ClaudeJudge `queued` ou `killed` → action mise en attente fondateur
   (file Tier 2)

## Convention de nommage

```
drafts/YYYY-MM-DD-<platform>-<slug>.md
campaigns/YYYY-MM-DD-<platform>.csv
recommendations/YYYY-MM-DD-<platform>-<scope>.md
```

- `<platform>` ∈ `{google_search, linkedin_sponsored, meta_image}`
- `<slug>` (drafts) = kebab-case `<objective>-<persona>` tronqué 50 chars
- `<scope>` (recommendations) = `weekly`, `monthly`, ou nom de campagne

## Statuts

### Drafts (`drafts/<file>.md`)
| Status | Sens | Qui transitionne |
|---|---|---|
| `draft` | Sortie du skill, en attente de relecture | skill `ads-creative-writer` |
| `validated` | Le fondateur a relu, prêt à pousser en plateforme | fondateur |
| `live` | Publié en plateforme (campaign_id renseigné) | fondateur (manuel jusqu'à P12.B) |
| `rejected` | Pas publié, raison dans le frontmatter | fondateur |

### Recommendations (`recommendations/<file>.md`)
| Status | Sens | Qui transitionne |
|---|---|---|
| `draft` | Sortie du skill, en attente de relecture | skill `ads-optimizer` |
| `validated` | Le fondateur a relu, prêt à appliquer | fondateur |
| `partially_applied` | Une partie des recos a été appliquée | fondateur |
| `fully_applied` | Toutes les recos appliquées | fondateur |

## Garde-fous breakers (P15)

- `ad_spend_runaway` : trip si dépense > 1.5× budget cible / 24h. Câblé
  côté `ads-optimizer` (P12 shadow) et sera réutilisé par AdBot agent
  Python (P12.B live).

## Liens

- Skill creative : [`.claude/skills/ads-creative-writer/SKILL.md`](../../.claude/skills/ads-creative-writer/SKILL.md)
- Skill optimizer : [`.claude/skills/ads-optimizer/SKILL.md`](../../.claude/skills/ads-optimizer/SKILL.md)
- Slash drafting : [`.claude/commands/draft-ad.md`](../../.claude/commands/draft-ad.md)
- Slash analysis : [`.claude/commands/analyze-ads.md`](../../.claude/commands/analyze-ads.md)
- Plan P12 full : [`docs/ARGOS_OPS_PLAN.md`](../../docs/ARGOS_OPS_PLAN.md) § Partie 12
- Breaker `ad_spend_runaway` : [`argos_ops/breakers.py`](../../argos_ops/breakers.py) (P15)
