# Argos Ops — Plan de branchement de la flotte

> **But** : recenser l'état exact de chaque bot (livré vs à brancher) pour
> savoir quoi connecter à quoi quand le moment sera venu.
>
> **Snapshot pris le** : 2026-05-27
> **Source de vérité code** : `argos_ops/agents/*.py` + `.env.local` + `.env.example`
>
> **Conventions de la note** :
> - ✅ **LIVE** — branché à un système externe réel, tourne en prod
> - 🟡 **LOCAL-DRAFT** — la logique fonctionne, produit des drafts sur disque, mais l'envoi/publish nécessite une action humaine ou un toggle à activer
> - ⏸ **PENDING** — code livré mais inactif tant que credentials/intégrations externes manquantes
> - ⚙️ **AUDIT-ONLY** — bot interne qui audit l'état du système (DB, filesystem) — n'a pas besoin d'API externe

---

## 1. Bots ✅ LIVE (branchés en production)

Ces bots tournent réellement et touchent à des systèmes externes. Aucune action requise pour les activer — vérifie juste les credentials ci-dessous.

### Email — IMAP/SMTP OVH Zimbra (`contact@omnividens.fr`)

| Bot | Rôle | Dépendance externe |
|---|---|---|
| **EmailBot** | Pull IMAP toutes les 15 min, classifie, push Discord | `EMAIL_*` env vars (✅ remplis) |

### Stripe (P7 FinanceBot)

| Bot | Rôle | Dépendance externe |
|---|---|---|
| **FinanceBot** | Sync Stripe quotidienne, MRR/ARR, dunning J+3/J+7/J+15 | `STRIPE_SECRET_KEY` ✅ · `STRIPE_WEBHOOK_SECRET` ⏸ (à brancher pour les webhooks live) · `FINANCEBOT_DUNNING_ENABLED=false` par défaut — bascule à `true` après audit wording |
| **InvoicePredictor** | Forecast cash flow 30/60/90j depuis Stripe | `STRIPE_SECRET_KEY` ✅ |
| **TaxBot** | Drafte TVA CA3 + IS prévisionnel depuis MRR Stripe | `STRIPE_SECRET_KEY` ✅ |
| **ReconcileBot** | Rapproche payouts Stripe ↔ CSV Qonto | `STRIPE_SECRET_KEY` ✅ + CSV Qonto dans `data/finance/` |

### Discord webhooks (4 canaux)

| Bot | Canal cible |
|---|---|
| **DigestBuilder** | `DISCORD_WEBHOOK_DIGEST` ✅ — digest quotidien 8h Paris |
| **BotHealthBot** | `DISCORD_WEBHOOK_OPS_LOGS` ✅ — silence si vert |
| **BotPerfAnalyzer** | `DISCORD_WEBHOOK_OPS_LOGS` ✅ |
| **ErrorTriageBot** | `DISCORD_WEBHOOK_OPS_LOGS` ✅ |
| **KillSwitchOperator** | `DISCORD_WEBHOOK_ALERTS` ✅ |
| **Tous les watchers `_watcher_base`** | utilise le webhook adapté au type d'alerte |
| _(optionnel)_ | `DISCORD_WEBHOOK_INBOX` ⏸ — fallback ESCALATIONS si vide |

### Infrastructure publique — HTTP / DNS / SSL

| Bot | Système externe | Credentials |
|---|---|---|
| **UptimeMonitor** | Ping URLs publiques via `httpx` | aucun — config dans `data/uptime/endpoints.yaml` |
| **DNSGuard** | Requêtes DNS publiques | aucun |
| **SSLExpirer** | Lecture cert TLS via socket | aucun |
| **DependencyAuditor** | `uv export` + osv.dev (public) | aucun |
| **CompetitorWatcher** | Scrape pages /pricing /features concurrents (HTTP public) | aucun |
| **BreachWatcher** | HIBP public API + flux CERT-FR | aucun |
| **CVEMonitor** | osv.dev public API | aucun |
| **RegulatoryWatcher** | RSS UE/CNIL/ANSSI | aucun |
| **DarkWebMonitor** | HIBP MVP (public) | aucun — extension dark web réelle = Phase ultérieure |
| **PressMonitor** | RSS / Google Alerts manuel — `data/comm/press_mentions.yaml` | manuel (pas de scraper auto) |

### Bots internes — sources DB / filesystem uniquement (⚙️ AUDIT-ONLY)

Ces bots ne touchent à aucun système externe — ils lisent la DB Argos Ops ou le filesystem du repo.

| Bot | Source |
|---|---|
| **BotHealthBot** | `agent_runs` + `breakers` |
| **BotPerfAnalyzer** | `agent_runs` (P50/P95) |
| **ErrorTriageBot** | `agent_runs.error` |
| **BotConfigManager** | diff `agent_config` DB ↔ `data/agent_config/baseline.yaml` |
| **KillSwitchOperator** | `breakers` |
| **OrchestratorBot** | `agent_config` + `breakers` + cron canonique |
| **LogAnomalyDetector** | `agent_runs` |
| **BackupVerifier** | filesystem `data/backups/` |
| **DocLinter** | filesystem `docs/`, `README.md`, `CLAUDE.md` |
| **StrategyBot** | DB CRM (MRR, leads, tickets) |
| **OKRTracker** | `data/okr/2026-Q2.yaml` |
| **BoardReporter** | DB CRM + `data/strategy/burn.yaml` |
| **DecisionLogger** | `docs/DECISIONS.md` |
| **BurnRateMonitor** | `data/strategy/burn.yaml` |
| **VendorContractWatcher** | `data/contracts/vendors.yaml` |
| **ExpenseAuditor** | `data/expenses/qonto_last.csv` (manuel) |
| **ContractDeadlineBot** | `data/contracts/clients.yaml` |
| **IncidentLogger** | `docs/incidents/*.md` |
| **RGPDAuditor** | `data/compliance/rgpd_registry.yaml` |
| **AIActComplianceBot** | métadonnées agents |
| **BloctelGuard** | `data/compliance/bloctel/bloctel_YYYY-MM.txt` (mensuel manuel) + `data/outbound/inbox/leads.csv` |
| **DealRiskScorer** | DB CRM (deals, interactions) |
| **ChurnPredictor** | DB CRM |
| **HealthScoreBot** | DB CRM |
| **UpsellSpotter** | DB CRM (usage / quotas) |
| **EscalationRouter** | DB tickets |
| **ChangelogBot** | `git log` |
| **ReleaseNotesBot** | `git log` + `data/release_notes/spec.yaml` |
| **FeedbackAggregator** | `data/feedback/items.yaml` (input manuel via EmailBot) |
| **RoadmapPublisher** | Annexe D `docs/ARGOS_OPS_PLAN.md` |
| **KBUpdater** | DB tickets + KB |
| **BrandGuardBot** | scan filesystem `data/*/drafts/*.md` |
| **CIFlakeTracker** | shell-out `gh` CLI (utilise auth `gh` locale — pas besoin de PAT) |
| **BugTriageBot** | `data/issues/open.yaml` (export manuel via `gh issue list`) |
| **DiagramGenerator** | `data/diagrams/<slug>.yaml` → `docs/diagrams/` |
| **ADRWriter** | `docs/adr/` |

### Public scraping sans auth — OK out-of-the-box

| Bot | Sources |
|---|---|
| **ProspectMiner** | Annonces légales BODACC + Crunchbase news RSS + LinkedIn Jobs RSS |
| **IntentSignalsBot** | Breach feeds publics + RSS embauches CISO + levées |

---

## 2. Bots 🟡 LOCAL-DRAFT (drafts produits, envoi humain)

Ces bots **fonctionnent dès maintenant** mais produisent des drafts en `.md` sur disque. Tu (ou un futur process automatisé) dois valider via l'Inbox du panel pour ensuite envoyer/publier via `zimbra-ops` ou les connecteurs sociaux. Pas de credentials manquants — l'humain-in-the-loop est délibéré.

### Sales — drafts à envoyer via Zimbra après validation

| Bot | Output | Destination après validation |
|---|---|---|
| **DemoFollowupBot** | `data/sales/demos/drafts/<id>.md` | Email envoyé via `zimbra-ops` |
| **MeetingBooker** | `data/sales/meetings/drafts/<id>.md` + .ics | Email confirmation via Zimbra |
| **ProposalBot** | `data/proposals/<deal_id>/*.md` + PDF pandoc | Email envoyé via Zimbra + signature manuelle |
| **ContractGenerator** | `data/contracts/<deal_id>/*.md` + PDF | Email envoyé via Zimbra |

### CS — drafts pour customer success

| Bot | Output |
|---|---|
| **OnboardingBot** | `data/onboarding/drafts/<customer>-J<step>.md` |
| **NPSCollector** | `data/nps/drafts/<customer>-<reason>.md` |
| **ReviewBot** | `data/reviews/drafts/<id>.md` |
| **TestimonialHunter** | `data/testimonials/drafts/<customer>.md` |

### Marketing — drafts contenu / outreach

| Bot | Output |
|---|---|
| **CaseStudyDrafter** | `data/blog/drafts/case-study-*.md` |
| **NewsletterBot** | `data/newsletters/drafts/YYYY-MM.md` |
| **BacklinkOutreach** | `data/seo/backlink_drafts/<slug>.md` |
| **WebinarPromoter** | `data/marketing/webinars/<id>/*.md` (3 posts + email teaser + replay) |
| **KeywordRadar** | `data/seo/movements-<date>.md` (shadow — pas de SERP scraper) |
| **LandingOptimizer** | `data/marketing/landing/<page>-ab-<date>.md` (shadow — attend Umami INFRA-02) |
| **TrendSpotter** | `data/trends/digest-<date>.md` (shadow — no scraping) |
| **MediaListBuilder** | `data/comm/media_list.yaml` (shadow — update manuel) |

### Communication — drafts presse / réponses

| Bot | Output |
|---|---|
| **PressReleaseDrafter** | `data/comm/press_releases/drafts/<id>.md` |
| **CrisisCommBot** | `data/comm/crisis_responses/drafts/<id>.md` |
| **SpokespersonPrep** | `data/comm/interview_prep/<id>.md` |
| **ReplyBot** | `data/social/reply_drafts/<mention_id>.md` (réponse LinkedIn / Mastodon) |

### Support — agents interactifs (slash commands)

| Bot | Mode | Slash |
|---|---|---|
| **SEOBot** | Health-check passif côté Python ; drafting interactif | `/generate-seo-brief` |
| **SupportBot** | Health-check passif ; RAG Tier 1 interactif | `/run-support-tier1` |

---

## 3. Bots ⏸ PENDING — branchements à finaliser

Ces bots **attendent une intégration externe** pour passer en LIVE. Tant que les credentials/services ne sont pas configurés, ils restent en shadow mode (drafts uniquement).

### 3.1 LinkedIn — publication organique (App #1 personnel + App #2 Page Omnividens)

**Bots concernés** :
- **ContentBot** (P9 live mode) — publie 2-5 posts/jour
- **ReplyBot** — répond aux mentions sociales
- **SocialAnalytics** — engagement reporting hebdo (lit l'API analytics LinkedIn)
- **WebinarPromoter** — teaser posts J-14/J-7/J-1

**À configurer dans `.env.local`** :
```
LINKEDIN_PAGE_ID=                # ✅ déjà rempli
LINKEDIN_PAGE_URN=               # ✅ déjà rempli
LINKEDIN_PERSONAL_CLIENT_ID=     # ✅ rempli (App #1)
LINKEDIN_PERSONAL_CLIENT_SECRET= # ✅ rempli
LINKEDIN_PERSONAL_ACCESS_TOKEN=  # ⏸ À OBTENIR — OAuth flow Sign In with LinkedIn
LINKEDIN_PAGE_CLIENT_ID=         # ✅ rempli (App #2)
LINKEDIN_PAGE_CLIENT_SECRET=     # ✅ rempli
LINKEDIN_PAGE_ACCESS_TOKEN=      # ⏸ À OBTENIR — Community Management API
```

**Setup** : générer les 2 access tokens via OAuth depuis LinkedIn Developer Portal (Apps Argos Ops + Argos Ops Page) → écrire dans `.env.local`.

**Activation** : ContentBot bascule auto en LIVE dès que `LINKEDIN_PAGE_ACCESS_TOKEN` est rempli (pas de toggle nécessaire — détection runtime).

### 3.2 Mastodon — publication organique

**Bots concernés** :
- **ContentBot** — posts Mastodon
- **ReplyBot** — réponses mentions

**À configurer** :
```
MASTODON_INSTANCE_URL=https://infosec.exchange   # ✅ déjà rempli
MASTODON_ACCESS_TOKEN=                            # ✅ déjà rempli
```

✅ **Déjà branché côté env**. Vérifie que le token est valide (test : `/draft-content` puis check publication).

### 3.3 Outbound cold email — envoi via domaine secondaire (P13.B live mode)

**Bots concernés** :
- **OutboundBot** (P13.A shadow) — scaffold de séquences cold email
- **OutboundSender** (P13.B live) — envoi SMTP des touches `drafted`

**À configurer** :
```
OUTBOUND_LIVE_MODE=false               # 🔒 garde-fou — bascule à true SEULEMENT après warmup domaine
OUTBOUND_DOMAIN=                       # ⏸ À ACHETER — ex. try-omnividens.com (~10€/an OVH)
OUTBOUND_FROM_DOMAIN=                  # ⏸ identique à OUTBOUND_DOMAIN
OUTBOUND_FROM_NAME=Argos par Omnividens
OUTBOUND_FROM_EMAIL=                   # ⏸ ex. contact@try-omnividens.com
OUTBOUND_UNSUBSCRIBE_SECRET=           # ⏸ À GÉNÉRER : python -c "import secrets; print(secrets.token_hex(32))"
OUTBOUND_DAILY_MAX=30                  # ✅ défaut 30 (warmup commence à 5)
```

**Setup** :
1. Acheter domaine secondaire (priority anti-bounce sur Omnividens principal)
2. Configurer SPF / DKIM / DMARC sur ce domaine (4 semaines de warmup minimum)
3. Générer le secret HMAC opt-out
4. Bascule progressive : `OUTBOUND_DAILY_MAX=5` semaine 1, 10 semaine 2, 30 en croisière
5. **Seulement après warmup réussi** : `OUTBOUND_LIVE_MODE=true`

### 3.4 Google Ads — pilotage live des campagnes (P12.B)

**Bots concernés** :
- **AdBot** (live mode) — applique les recommandations chiffrées

**À configurer** :
```
GOOGLE_ADS_DEVELOPER_TOKEN=    # ⏸ À OBTENIR — Google Ads API console
GOOGLE_ADS_CLIENT_ID=          # ⏸
GOOGLE_ADS_CLIENT_SECRET=      # ⏸
GOOGLE_ADS_REFRESH_TOKEN=      # ⏸ OAuth flow
ADS_LIVE_MODE=false            # 🔒 garde-fou — bascule SEULEMENT après audit recos
```

**Setup** : Google Ads Manager → API console → générer OAuth credentials + obtenir developer token (review Google ~7j) → script `scripts/google_ads_auth.py` (à créer si besoin) pour récupérer refresh token.

**Note D-026** : passage live conditionné à un budget pub validé par le fondateur.

### 3.5 Meta Ads (Facebook / Instagram)

**Bots concernés** :
- **AdBot** — pilotage campagnes Meta

**À configurer** :
```
META_ADS_ACCESS_TOKEN=         # ⏸ Long-lived user token via Graph API Explorer
META_ADS_AD_ACCOUNT_ID=        # ⏸ ID du compte pub Meta Business
```

**Setup** : Meta Business Suite → System User → générer un long-lived token (60 jours, à renouveler) avec scope `ads_management`.

### 3.6 LinkedIn Ads (App séparée des posts organiques)

**Bots concernés** :
- **AdBot** — campagnes LinkedIn Sponsored

⚠️ **Pas dans `.env.example` actuellement** — à ajouter quand le bot LinkedIn Ads sera activé :
```
LINKEDIN_ADS_ACCESS_TOKEN=
LINKEDIN_ADS_ACCOUNT_ID=
```

### 3.7 Umami self-host (INFRA-02 — analytics omnividens.fr)

**Bots concernés** :
- **LandingOptimizer** — propose variantes A/B basées sur les heatmaps Umami
- **SocialAnalytics** (partiellement) — cross-référence traffic ↔ posts

**À configurer après déploiement Umami** :
```
UMAMI_BASE_URL=                # ⏸ ex. https://analytics.omnividens.fr
UMAMI_USERNAME=                # ⏸
UMAMI_PASSWORD=                # ⏸
UMAMI_WEBSITE_ID=              # ⏸ UUID du site dans Umami
```

**Setup** : INFRA-02 = déployer Umami self-hosted sur le serveur (Docker, sous-domaine `analytics.omnividens.fr`). Puis créer un compte admin et noter le website_id.

### 3.8 Stripe webhook secret (sécurité dunning live)

**Concerne** : `FinanceBot` quand on activera la réception de webhooks Stripe (paiement réussi, échec, etc.).

```
STRIPE_WEBHOOK_SECRET=         # ⏸ À OBTENIR depuis Stripe Dashboard → Developers → Webhooks
```

**Setup** : Stripe Dashboard → ajouter un endpoint `https://omnividens.fr/api/stripe/webhook` (à exposer côté backend) → copier le signing secret.

### 3.9 Admin Control Panel — auth basic + IP allowlist + TOTP (P16.B / P16.D)

**À configurer pour la prod** (le panel local n'en a pas besoin) :
```
OPS_DASHBOARD_BASIC_AUTH_USER=        # ⏸
OPS_DASHBOARD_BASIC_AUTH_PASSWORD=    # ⏸ hash bcrypt ou plain (Caddy hash)
OPS_DASHBOARD_JWT_SECRET=             # ⏸ token_hex(32)
OPS_DASHBOARD_IP_ALLOWLIST=           # ⏸ ex. "82.x.x.x,2001:db8::1"
OPS_DASHBOARD_TOTP_SECRET=            # ⏸ P16.D (2FA)
```

### 3.10 BountyRadar — pas encore implémenté

**Statut** : module `argos_ops/agents/bounty_radar.py` existe mais reste un stub (cf. docstring « Sprint 6+ »). Aucune action requise — bot dormant en attendant qu'on définisse la source des bug bounty.

---

## 4. Roadmap d'activation suggérée (ordre logique)

### Sprint A — gains immédiats (zéro $)
1. **Mastodon** — token déjà rempli, valide-le en lançant `/draft-content` → publish manuel sur Mastodon
2. **LinkedIn perso (App #1)** — OAuth flow pour récupérer `LINKEDIN_PERSONAL_ACCESS_TOKEN` (60 min de setup, gratuit)
3. **Stripe webhook secret** — 5 min sur le dashboard une fois qu'un endpoint est exposé

### Sprint B — outbound (~10€/an)
4. **Acheter `try-omnividens.com`** chez OVH
5. **Configurer SPF/DKIM/DMARC** + ajouter au compte Zimbra OVH (ou serveur SMTP dédié)
6. **Warmup 4 semaines** : OUTBOUND_DAILY_MAX = 5, puis 10, puis 30
7. **Activer OUTBOUND_LIVE_MODE=true** après warmup

### Sprint C — quand le budget pub est validé
8. **Google Ads** — OAuth flow + developer token review (~7j attente Google)
9. **Meta Ads** — System User + long-lived token
10. **LinkedIn Ads** — ajouter `LINKEDIN_ADS_*` à `.env.example` + .env.local
11. **Activer ADS_LIVE_MODE=true** une fois les credentials des 3 plateformes en place

### Sprint D — analytics avancées
12. **Déployer Umami** sur `analytics.omnividens.fr` (Docker compose à côté de Caddy)
13. **Configurer `UMAMI_*`** + ajouter le tag tracker sur `omnividens.fr`
14. **LandingOptimizer** se branche automatiquement

### Sprint E — prod hardening Admin Panel
15. **OPS_DASHBOARD_*** : auth basic + JWT secret + IP allowlist
16. **Caddy basic auth** devant le panel
17. **TOTP 2FA** (P16.D) une fois la base auth stable

---

## 5. Crédentials actuellement présents dans `.env.local`

> Audit du 2026-05-27 — fichier `.env.local` réel sur cette machine.

### ✅ Remplis (working)
- `ARGOS_OPS_LOG_LEVEL` · `DATABASE_URL` · `REDIS_URL`
- `GEMINI_API_KEY` (mais inutilisé — D-017 acte qu'on n'appelle plus d'API LLM tierce)
- 4 webhooks Discord + `DISCORD_FOUNDER_USER_ID`
- `MASTODON_INSTANCE_URL` + `MASTODON_ACCESS_TOKEN`
- `LINKEDIN_PAGE_ID` + `LINKEDIN_PAGE_URN` + 2 client_id/secret (Apps #1 et #2)
- 7 vars `EMAIL_*` (IMAP/SMTP Zimbra) + signature
- `STRIPE_SECRET_KEY`

### ⏸ Vides — à brancher
- `DISCORD_WEBHOOK_INBOX` (optionnel — fallback ESCALATIONS)
- `LINKEDIN_PERSONAL_ACCESS_TOKEN` + `LINKEDIN_PAGE_ACCESS_TOKEN` ← **2 tokens à obtenir en priorité**
- `GMAIL_*` (déprécié D-018 — ignore)
- `STRIPE_WEBHOOK_SECRET`
- `GOOGLE_ADS_*` (4 vars)
- `META_ADS_*` (2 vars)
- `UMAMI_*` (4 vars) — bloqué sur INFRA-02
- `OPS_DASHBOARD_*` (5 vars) — pour la prod
- `OUTBOUND_*` (4 vars) — bloqué sur achat domaine

### ❌ Vars Reddit (REDDIT_CLIENT_ID, etc.)
Retirées du périmètre par **D-022 (2026-05-15)** — peuvent rester vides ou être supprimées de `.env.local`.

---

## 6. Tableau récap (vision aérienne)

| Catégorie | Total bots | ✅ Live | 🟡 Local-draft | ⏸ Pending | ⚙️ Audit-only |
|---|---|---|---|---|---|
| **Direction & Stratégie** | 4 | 4 | 0 | 0 | 4 |
| **Finance & Trésorerie** | 7 | 5 | 0 | 1 (webhook) | 4 |
| **Sales / Commercial** | 9 | 4 | 4 | 1 (outbound live) | 1 |
| **Marketing & Growth** | 12 | 0 | 8 | 4 (LinkedIn / Ads / Umami) | 0 |
| **Customer Success & Support** | 9 | 2 | 5 | 0 | 2 |
| **Produit & R&D** | 5 | 5 | 0 | 0 | 5 |
| **Tech / SRE / Sécurité IT** | 8 | 8 | 0 | 0 | 8 |
| **Veille & Threat Intel** | 6 | 5 | 0 | 1 (dark web pro) | 0 |
| **Juridique & Compliance** | 5 | 5 | 0 | 0 | 5 |
| **Communication** | 8 | 1 (EmailBot) | 6 | 1 (LinkedIn Page) | 0 |
| **Documentation** | 3 | 3 | 0 | 0 | 3 |
| **Meta-Ops** | 7 | 7 | 0 | 0 | 7 |
| **TOTAL** | ~83 | 49 | 23 | 8 | 39 |

_Note : un bot peut compter dans plusieurs colonnes (ex. un audit-only est aussi live)._

---

## 7. Décisions structurantes liées (rappel)

- **D-017** (2026-05-08) — Argos Ops 100 % local-first. Aucune API LLM tierce, jamais.
- **D-018** (2026-05-08) — Stack email = OVH Zimbra IMAP/SMTP (pas Gmail).
- **D-022** (2026-05-15) — Reddit retiré du périmètre (vars peuvent être nettoyées).
- **D-026** — Passage AdBot live conditionné à un budget pub validé.

Cf. [`docs/DECISIONS.md`](docs/DECISIONS.md) pour le détail.

---

## 8. Quand brancher = quand débloquer

Quand tu seras prêt à brancher un bot, suis ce check-list :

1. **Identifie le bot dans la section 3** ci-dessus
2. **Remplis les env vars** correspondantes dans `.env.local` (jamais dans `.env.example`)
3. **Restart le backend** : `Ctrl+C` sur uvicorn + relance `uv run python scripts/run_ops_dashboard.py`
4. **Vérifie le statut côté panel** :
   - Ouvre la page du bot dans le catalogue
   - Vérifie section « Skills & dépendances » → les env vars listées doivent matcher
   - Click « Run now » pour valider que ça tourne sans erreur
5. **Pour les bots live mode (Ads / Outbound)** : active le `*_LIVE_MODE=true` SEULEMENT après audit manuel d'un draft / une reco
6. **Documenter dans `docs/DECISIONS.md`** si c'est une bascule structurante (ex. passage live outbound)
