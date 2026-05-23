---
session: PROMPT-5
date: 2026-05-23
branch: feat/p22g-cs-produit-13-bots
scope: Sprint 7 CS (8 bots) + Sprint 11 Produit (5 bots) = 13 bots
status: complete-local
---

# P22.G — Session 5 récap

## Livré

**Customer Success (Sprint 7 — 8 bots)** :
1. `OnboardingBot` — drafts emails J+0/J+7/J+30 depuis `data/cs/customers.yaml`
2. `HealthScoreBot` — score santé 0-100 + snapshot `data/health_scores/snapshot_<date>.yaml`
3. `KBUpdater` — cluster tickets répétés → drafts squelette `data/knowledge_base/drafts/<slug>.md`
4. `NPSCollector` — drafts NPS J+14 onboarding + J+21 renew
5. `UpsellSpotter` — comptes usage ≥ 80% quota → `data/upsell/candidates_<date>.yaml`
6. `EscalationRouter` — tri tickets P0/P1/P2 + SLA breach → `data/support/triage_<date>.yaml`
7. `ReviewBot` — drafts demande G2/Capterra (promoteurs NPS ≥ 9 uniquement)
8. `ChurnPredictor` — signaux pré-churn cumulés + snapshot `data/churn/at_risk_<date>.yaml`

**Produit (Sprint 11 — 5 bots)** :
9. `ChangelogBot` — `git log` entre refs → `data/public/changelog_<slug>.md` (conventional commits regroupés)
10. `ReleaseNotesBot` — depuis `data/release_notes/spec.yaml` → `data/public/release_notes/<version>.md` (ton user-friendly)
11. `FeedbackAggregator` — `data/feedback/items.yaml` → clustering exact par `topic` → digest
12. `RoadmapPublisher` — parse Annexe D → `data/public/roadmap.md` (codes sprint retirés)
13. `BugTriageBot` — `data/issues/open.yaml` → tri P0/P1/P2 + label suggéré (read-only)

## Architecture posée

- `argos_ops/cs/` (4 modules) : `models`, `loader`, `scoring`, `templates` partagés par les 8 bots CS.
- `argos_ops/product/` (2 modules) : `git_history` (subprocess `git log`), `annexe_d_parser` (regex Annexe D).

Toutes les heuristiques sont explicites (pas de ML) — auditabilité RGPD § 22.

## Commits locaux

3 commits sur `feat/p22g-cs-produit-13-bots` :
1. `feat(p22g-cs-1)` — OnboardingBot + HealthScoreBot + KBUpdater + NPSCollector (23 fichiers)
2. `feat(p22g-cs-2)` — UpsellSpotter + EscalationRouter + ReviewBot + ChurnPredictor (16 fichiers)
3. `feat(p22g-produit+meta)` — 5 bots Produit + Annexe D + agentCatalog + summary

**Zéro push** — conforme à la consigne `INTERDIT git push / gh pr create`.

## Tests

86 tests verts (`uv run pytest tests/test_cs_*.py tests/test_onboarding_bot.py tests/test_health_score_bot.py tests/test_kb_updater.py tests/test_nps_collector.py tests/test_upsell_spotter.py tests/test_escalation_router.py tests/test_review_bot.py tests/test_churn_predictor.py tests/test_changelog_bot.py tests/test_release_notes.py tests/test_feedback_aggregator.py tests/test_roadmap_publisher.py tests/test_bug_triage.py`).

Couvre :
- Scoring (health, upsell, churn, SLA, classification ticket)
- Loader YAML (round-trip, missing file, partial entries)
- Drafts email (frontmatter + corps templaté)
- Embeds Discord (couleur selon état)
- Git history parsing (conventional commits + breaking changes)
- Parser Annexe D (regex robust face aux variantes de format)

## Slash commands installés

13 nouvelles slash commands `.claude/commands/` :
- `/run-onboarding`, `/run-health-scores`, `/draft-kb-update`, `/run-nps-campaign`
- `/run-upsell-spots`, `/run-ticket-triage`, `/run-review-campaign`, `/run-churn-predict`
- `/draft-changelog`, `/draft-release-notes`, `/run-feedback-digest`, `/publish-roadmap`, `/run-bug-triage`

## Mode

Tous les bots tournent en **mode shadow / humain-in-the-loop strict** :
- Bots qui draftent (Onboarding, NPS, Review, KBUpdater, ReleaseNotes) → écrivent dans `data/<bot>/drafts/`, founder valide et envoie via `zimbra-ops`.
- Bots scoring (HealthScore, Upsell, Churn) → snapshots YAML + Discord, zéro action automatique.
- BugTriageBot → suggère labels, **n'applique pas** via `gh api`.
- ChangelogBot + RoadmapPublisher → écrivent dans `data/public/`, founder revue avant push site.

## Skills réutilisés (lecture seule — pas de réécriture)

- `kb-rag` (P6) — utilisé en aval par `/draft-kb-update`
- `claude-judge` (P14) — invoqué côté slash command pour ReviewBot, NPSCollector, KBUpdater, ReleaseNotesBot
- `zimbra-ops` (D-018) — envoi humain des drafts CS
- `email-classifier` (P5) — pas re-imported, mais cohérence respectée
- `stripe-ops` (P7) — pas consommé dans cette session (intégration future via daily-finance-sync)

## Annexe D — compteur mis à jour

- Avant : `34 actifs + 1 skill = 35` / `43 roadmap`
- Après : `47 actifs + 1 skill = 48` / `30 roadmap`
- Delta net : `+13` actifs / `-13` roadmap

§5 CS : 8 lignes passées `[x] ✅ ... *P22.G livré 2026-05-23.*` (SupportBot déjà coché).
§6 Produit : 5 lignes passées `[x] ✅ ... *P22.G livré 2026-05-23.*`.

## agentCatalog.ts

13 entrées passées de `status: "roadmap"` (avec `roadmapRef`) à `status: "active"` (avec `name` non-null = backend Python attendu).

## Coordination inter-sessions

État détecté au début de cette session : repo en cours de churn avec 6+ sessions parallèles (P22.B, C, D, F, H, I). Les fichiers Annexe D + agentCatalog ont été modifiés / partiellement reset pendant ma session par d'autres process — j'ai pris l'état actuel en working tree comme référence et appliqué mes 13 deltas dessus.

Aucune réécriture des skills `kb-rag`, `claude-judge`, `zimbra-ops`, `stripe-ops` — lecture seule respectée.

## Session 5 OK, prêt pour consolidation.
