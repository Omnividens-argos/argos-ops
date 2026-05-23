---
session: P22i — Sprint Marketing / Comm / activation P11 / P9 full / P12.B live
date: 2026-05-23
status: drafted
---

# Decisions structurantes — Prompt 7 (P22i)

Ces 3 décisions touchent des **gates externes** au code Argos Ops. Elles
sont actées en draft ici et seront promues vers `docs/DECISIONS.md` une
fois que le founder confirme les valeurs (tokens, budgets) requises pour
basculer en mode live.

---

## D-024 — Activation LinkedIn API (gate de ContentBot live mode)

**Date** : 2026-05-23
**Statut** : drafted (gate ouvert, attente token founder)

### Contexte

ContentBot (P9 full, livré P22i LOT A) supporte la publication réelle sur
LinkedIn via l'endpoint `POST /v2/ugcPosts` (LinkedIn Marketing API). Le
client [`argos_ops.social.linkedin`](../../argos_ops/social/linkedin.py)
tourne en **shadow mode** tant que `LINKEDIN_API_TOKEN` + `LINKEDIN_ORG_URN`
ne sont pas configurés dans `.env.local`.

### Décision

Tant que ContentBot reste en shadow (drafts publiés vers
`data/content/published/` avec `status: published_shadow`), aucun risque
audience. Le passage en live demande :

1. **Création d'une LinkedIn Developer App** sur https://www.linkedin.com/developers/
2. **Scopes requis** :
   - `w_member_social` (publier sur le profil founder)
   - `w_organization_social` (publier sur la page Omnividens si créée)
3. **Token OAuth2 court-terme** (60 jours) — à renouveler manuellement
   ou via futur OAuthRefreshBot
4. **URN de l'organisation** (ex : `urn:li:organization:12345`) à
   récupérer via `GET /v2/organizations`
5. **Test en sandbox** : publier 1 post via `/publish-content` sur un
   compte test avant production

### Pourquoi en draft et pas dans `docs/DECISIONS.md`

Le founder doit explicitement confirmer :
- Qu'il accepte de publier 2-5 posts/jour automatisés sur sa page
- Que le ton produit par `content-writer` lui convient en condition réelle
- Que le cap `CONTENT_DAILY_MAX_PER_CHANNEL` (défaut 3) est cohérent
  avec son audience

Une fois ces 3 confirmations + token créé → promote D-024 dans
`docs/DECISIONS.md`.

---

## D-025 — Activation Mastodon API (gate de ContentBot live mode)

**Date** : 2026-05-23
**Statut** : drafted (gate ouvert, attente token founder)

### Contexte

ContentBot supporte aussi Mastodon via `POST /api/v1/statuses`
([`argos_ops.social.mastodon`](../../argos_ops/social/mastodon.py)).
Instance par défaut : `https://infosec.exchange` (audience cyber +
décentralisé, cohérent avec le local-first dogma D-017).

### Décision

Le passage en live demande :

1. **Compte Mastodon Omnividens** sur `infosec.exchange` (ou autre
   instance — override via `MASTODON_INSTANCE_URL`)
2. **Token d'accès** créé dans Settings → Development sur l'instance,
   scopes `write:statuses`
3. **Test en sandbox** : tooter 1 message via `/publish-content` sur
   un compte test

L'instance peut être changée sans redéploiement (settings env).
Reddit reste exclu du périmètre par [D-022](../../docs/DECISIONS.md#d-022).

### Pourquoi en draft

Cohérence avec D-024 — même validation founder requise. Choix
d'instance final à confirmer (infosec.exchange vs piaille.fr vs autre).

---

## D-026 — Budget pub validé (gate de AdBot live mode)

**Date** : 2026-05-23
**Statut** : drafted (gate ouvert, attente confirmation budget)

### Contexte

AdBot (P12.B live mode, livré P22i LOT A) consomme les recommandations
chiffrées (€/semaine) produites par le skill `ads-optimizer` et peut les
appliquer sur Google Ads / LinkedIn Campaign Manager / Meta Ads
Manager. Tant que `ADS_LIVE_MODE=false` ET `ADS_DAILY_BUDGET_EUR=0`, le
bot reste en shadow (archive les actions dans
`data/ads/applied/<timestamp>-<platform>-<action>.yaml` avec
`status: shadow`).

### Décision

Le passage en live demande, dans l'ordre :

1. **Backtest 4 semaines minimum** : produire 4 CSV `/analyze-ads` sur
   un trafic shadow réel (depuis Google Search Console / outils
   organic), valider que les recommandations auraient été cohérentes
   si appliquées
2. **Budget pub mensuel validé founder** — proposition :
   - **Phase 1** : 300 €/mois (10 €/jour) — Google Ads keywords ICP
     uniquement, AdBot peut auto-pause / auto-scale dans ce cap
   - **Phase 2** : 600 €/mois (20 €/jour) après 4 semaines stables
   - **Phase 3** : LinkedIn Sponsored Content après ProspectMiner P22h
     stable (cibles ICP enrichies)
3. **Activation progressive** :
   - `ADS_LIVE_MODE=true` + `ADS_DAILY_BUDGET_EUR=10` (phase 1)
   - Token Google Ads developer requis
   - Breaker `ad_spend_runaway` (P15) opérationnel (déjà câblé via
     `argos_ops.breakers`)

### Garde-fous opérationnels

Le code AdBot live applique 2 sécurités automatiques :

- **Cap budget par action** : si la somme des `|delta|/7` d'une reco
  dépasse `ADS_DAILY_BUDGET_EUR`, l'action est archivée avec
  `status: blocked_budget_cap` et ne touche pas l'API
- **Breaker `ad_spend_runaway` (P15)** : tripe le bot complet si
  dépense réelle > budget — protection contre dérive

### Pourquoi en draft

Le founder doit confirmer :
- Le budget mensuel acceptable (proposition phase 1 : 300 €/mois)
- L'acceptation du risque de runaway (mitigé par breaker)
- Le compte Google Ads / Meta Business actif et lié à
  `omnividens.fr` pour vérification de propriété

---

## Suivi

Une fois les 3 gates confirmés (D-024 + D-025 + D-026) → promouvoir
ces décisions dans [`docs/DECISIONS.md`](../../docs/DECISIONS.md) avec
les valeurs réelles et dates de bascule. Reset des breakers
correspondants si tripés pendant la phase de bascule.
