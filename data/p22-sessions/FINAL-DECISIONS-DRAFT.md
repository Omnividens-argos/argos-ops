---
draft: décisions structurantes D-023 → D-027 (consolidation P22.D)
date: 2026-05-23
status: drafted — à promouvoir dans docs/DECISIONS.md après merge PRs
---

# Décisions structurantes — méta-sprint P22.D (Prompts 2-7)

Numéros réservés et contenu prêt à coller dans
[`docs/DECISIONS.md`](../../docs/DECISIONS.md) après que les 6 PRs soient
mergées. Si une décision est déjà occupée par un autre flow entre temps,
décaler vers le prochain numéro libre.

---

## D-023 — Activation OutboundBot P13.B en mode `stage` (fallback du domaine secondaire)

**Source** : PROMPT-6 (P22.H Sales).
**Statut** : drafted (code livré, gate domaine secondaire).

**Décision** : livrer le pipeline outbound SMTP réel
(`argos_ops/agents/outbound_sender.py`, slash `/send-outbound-batch`) en
**mode `stage`** par défaut, tant que le domaine secondaire n'est pas
acquis et warmé-up. En stage, expéditeur = `contact@omnividens.fr`,
destinataire rerouté vers cette même boîte, sujet préfixé `[STAGE]`,
footer RGPD + AI Act + opt-out HMAC inclus. Bascule en live par flip de
3 variables `.env.local` :
- `OUTBOUND_LIVE_MODE=true`
- `OUTBOUND_FROM_DOMAIN=<domaine>`
- `OUTBOUND_UNSUBSCRIBE_SECRET=<hex 64>`

**Pourquoi** :
- Domaine secondaire non encore acquis au 2026-05-23 (bloqueur explicite prompt P22.H).
- Stage mode permet de valider rendering / footer RGPD / threading SMTP / idempotence sans risque réputation `omnividens.fr`.
- 8 autres bots Sales dépendent du même chemin SMTP — bloquer P13.B casserait l'orchestration cross-bot.

**Implication** :
- Tests `tests/test_outbound_live.py` couvrent les 3 modes (stage/live/disabled).
- Le breaker `OutboundBot` (P15) est partagé entre scaffold (P13.A) et envoi (P13.B).

**Suivi** :
- [ ] Founder : acheter domaine secondaire + SPF/DKIM/DMARC.
- [ ] Warmup 4 semaines en stage avant flip live (cap `OUTBOUND_DAILY_MAX=30`).
- [ ] Au flip live, Annexe D §3 ligne `OutboundBot` passe de `[~] 🟡` à `[x] ✅` + nouvelle décision audit délivrabilité Bloctel.

---

## D-024 — Activation LinkedIn API (gate ContentBot live mode)

**Source** : PROMPT-7 (P22.I Marketing/Comm).
**Statut** : drafted (gate ouvert, attente token founder).

**Décision** : ContentBot (P9 full) supporte la publication LinkedIn via `POST /v2/ugcPosts`, mais reste en **shadow mode** tant que `LINKEDIN_API_TOKEN` + `LINKEDIN_ORG_URN` ne sont pas configurés. Drafts publiés vers `data/content/published/` avec `status: published_shadow`.

**Pré-requis pour passer en live** :
1. Création LinkedIn Developer App.
2. Scopes : `w_member_social` + `w_organization_social`.
3. Token OAuth2 60j (renouvellement manuel ou futur OAuthRefreshBot).
4. URN organisation via `GET /v2/organizations`.
5. Test sandbox sur compte test.

**Confirmations founder requises avant promote** :
- Acceptation publication 2-5 posts/jour automatisée.
- Validation du ton `content-writer` en condition réelle.
- Cap `CONTENT_DAILY_MAX_PER_CHANNEL` (défaut 3) cohérent avec l'audience.

---

## D-025 — Activation Mastodon API (gate ContentBot live mode)

**Source** : PROMPT-7.
**Statut** : drafted.

**Décision** : ContentBot supporte Mastodon via `POST /api/v1/statuses`
([`argos_ops/social/mastodon.py`](../../argos_ops/social/mastodon.py)).
Instance par défaut : `https://infosec.exchange` (audience cyber + décentralisé, cohérent avec D-017 local-first dogma). Override possible via `MASTODON_INSTANCE_URL`.

**Pré-requis** :
1. Compte Mastodon Omnividens (instance à confirmer).
2. Token d'accès scopes `write:statuses`.
3. Test sandbox.

Reddit reste exclu du périmètre par [D-022](../../docs/DECISIONS.md#d-022).

---

## D-026 — Budget pub validé (gate AdBot live mode)

**Source** : PROMPT-7.
**Statut** : drafted.

**Décision** : AdBot (P12.B live mode, livré P22.I LOT A) consomme les
recommandations d'`ads-optimizer` et peut les appliquer sur
Google/LinkedIn/Meta Ads. Reste en shadow tant que `ADS_LIVE_MODE=false`
ET `ADS_DAILY_BUDGET_EUR=0`.

**Activation progressive** :
1. **Backtest 4 semaines** sur trafic shadow réel.
2. **Phase 1** : 300 €/mois (10 €/jour) — Google Ads keywords ICP uniquement, auto-pause / auto-scale dans ce cap.
3. **Phase 2** : 600 €/mois (20 €/jour) après 4 semaines stables.
4. **Phase 3** : LinkedIn Sponsored après ProspectMiner P22.H stable.

**Garde-fous opérationnels** :
- Cap budget par action : `|delta|/7` > `ADS_DAILY_BUDGET_EUR` → `status: blocked_budget_cap`.
- Breaker `ad_spend_runaway` (P15) trip le bot complet si dépense > budget.

**Confirmations founder requises** :
- Budget mensuel acceptable (proposition phase 1 : 300 €/mois).
- Acceptation du risque runaway (mitigé par breaker).
- Compte Google Ads / Meta Business lié à `omnividens.fr` (vérification propriété).

---

## D-027 — Sessions parallèles d'agents IA = obligation de worktree isolé

**Source** : retex consolidation P22.D 2026-05-23.
**Statut** : à valider founder.

**Décision** : pour tout méta-sprint où 2+ sessions tournent en parallèle sur le même repo Argos Ops, chaque session **DOIT** opérer dans un git worktree isolé (ou un répertoire cloné séparé), jamais sur le même working tree partagé.

**Pourquoi** : la session de consolidation P22.D du 2026-05-23 a découvert que les 6 Prompts 2-7 avaient en réalité travaillé sur le même working tree séquentiellement, ce qui a produit :
- Cross-contamination de fichiers partagés (Annexe D, agentCatalog.ts, config.py) via auto-merge de cherry-pick.
- Doublons SHAs (mêmes contenus committés 2× sur 2 branches).
- HEADs de branches mal-attribués (p22d pointait sur un commit p22h-amont).
- Working tree pollué (14 fichiers untracked d'une session précédente).
- Summaries non corroborés par les commits réels (PROMPT-4 disait modifier Annexe D, les commits ne le faisaient pas).

**Coût payé** : ~2h de session pour reconstruire 6 branches propres via cherry-pick from main + fix commits mypy/ruff.

**Implication technique** :
- Outil disponible : `Agent` tool avec `isolation: "worktree"`.
- Pour les sessions humaines parallèles : `git worktree add ../argos-ops-p22X feat/p22X-<name>`.
- Le founder reste responsable de la sérialisation des merges (PRs ordonnées dans CONSOLIDATION-REPORT.md).

**Pas une régression** : les 67 bots livrés sont fonctionnellement corrects (824 tests verts au total), la dette est uniquement organisationnelle et a été remboursée intégralement par cette session de consolidation.

---

## Suivi

Une fois les 6 PRs P22.D mergées :
1. Promouvoir D-023 → D-027 dans [`docs/DECISIONS.md`](../../docs/DECISIONS.md).
2. Ajouter un commit "tracking sync" sur main pour réconcilier le compteur Annexe D final (`✅ 83 / 🟡 1 / ⬜ 2`) — uniquement après les 6 merges.
3. Supprimer les branches locales `*-pre-consolidation` (`git branch -D feat/p22X-...-pre-consolidation`) après validation que tout est en place.
4. Dropper le stash `p22-pollution-untracked-2026-05-23` une fois p22h merge sur main.
