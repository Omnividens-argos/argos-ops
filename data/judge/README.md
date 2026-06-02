# `data/judge/` — fixtures & calibration agent-juge Tier 1 (P14)

Cas golden pour calibrer et régression-tester le skill
[`claude-judge`](../../.claude/skills/claude-judge/SKILL.md).

## Convention

Chaque fixture = 1 fichier YAML dans `fixtures/` avec :

```yaml
id: 001
title: <slug-court>
verdict_attendu: auto_send | queued | killed
axe_critique: factual | tone | legal | global
notes: <pourquoi ce cas est golden — la régression qu'on prévient>

input:
  channel: email | social_linkedin | social_mastodon | social_bluesky | social_meta | social_x | social_truth | blog | stripe_dunning
  agent_name: EmailBot | SupportBot | ContentBot | OutboundBot | FinanceBot | SEOBot
  original_query: <ce qui a déclenché le draft>
  draft: |
    <texte complet du draft à juger>
  rag_chunks: |
    <chunks KB chargés, ou null si pas de RAG>

expected:
  factual_score_band: [min, max]   # ex [85, 100]
  tone_score_band: [min, max]
  legal_score_band: [min, max]
  global_score_band: [min, max]
  verdict: auto_send | queued | killed
  factual_issues_must_include: []   # substring qui doit apparaître
  tone_issues_must_include: []
  legal_issues_must_include: []
```

## Workflow de calibration

1. Quand on observe un faux positif (auto_send sur un draft qui aurait
   dû être queued) ou un faux négatif (killed sur un draft propre) en
   prod → **ajouter** le cas aux fixtures
2. Re-jouer toutes les fixtures via `claude-judge` (boucle manuelle
   pour l'instant, un script `scripts/eval_judge.py` à écrire en P14.1)
3. Si > 1 faux verdict → ajuster soit le prompt skill, soit
   `apply_thresholds` dans `argos_ops/judge.py`
4. Commit fixture + ajustement dans le même PR

**Règle** : on ne supprime jamais une fixture qui passait. On n'ajuste
les seuils que si une fixture mal calibrée le mérite (avec explication
en commit message).

## Inventaire actuel (5 starter, target 50)

| ID | Title | Verdict | Axe critique |
|----|-------|---------|--------------|
| 001 | email_factuel_clean | auto_send | global propre |
| 002 | email_hallucination_prix | killed | factual |
| 003 | linkedin_buzzword_innovant | queued | tone |
| 004 | outbound_pas_optout | killed | legal |
| 005 | seo_brief_disparage_burp | queued | legal modéré |

## Cas à ajouter (backlog P14.1)

Couverture manquante :

- Mastodon emoji cascade → queued (tone)
- Email mention PII tiers nominative → killed (legal hard)
- Dunning J+15 ton agressif → queued (tone)
- Blog brief KB-sourced clean → auto_send (cas miroir 001 sur blog)
- Outbound conforme RGPD + opt-out + disclosure → auto_send
- Réponse support hors-KB hallucination feature inventée → killed
- Email contenant token / secret leak → killed
- Comm bilingue FR/EN cohérence tu/vous → queued
- Dunning amical J+3 vs ferme J+7 — séparer 2 fixtures
