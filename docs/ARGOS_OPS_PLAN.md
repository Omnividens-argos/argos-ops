# Argos Ops — Plan de mise en place

> Système d'agents IA qui font tourner l'acquisition, la conversion, le support et l'admin
> autour d'un fondateur solo, en s'appuyant uniquement sur l'abonnement Claude Pro/Max comme
> runtime de pensée et des APIs gratuites pour la plomberie.
>
> **Cible** : `omnividens.fr` (Argos / SecHunter SaaS pentest BtoB).
> **Contrainte budgétaire** : 0 € de SaaS récurrent en plus de l'abonnement Claude existant.
> **Mode opératoire** : chaque partie ci-dessous est conçue pour être prise par une session
> Claude Code indépendante. Les prérequis sont explicites, les livrables aussi.

---

## Sommaire

| Partie | Titre | Sprint | Skill(s) à invoquer |
|--------|-------|--------|---------------------|
| 0 | Vision et décisions préalables | — | — |
| 1 | Préparation technique et choix d'hébergement | — | — |
| 2 | Bootstrap du dossier `argos-ops` | Sprint 0 | — |
| 3 | Schéma CRM + Knowledge Base | Sprint 0 | — |
| 4 | Premier slash command — `/morning-digest` | Sprint 0 | `skill-creator` |
| 5 | EmailBot inbound | Sprint 1 | `skill-creator` |
| 6 | SupportBot Tier 1 (RAG sur KB) | Sprint 1 | `skill-creator` |
| 7 | FinanceBot (Stripe + relances) | Sprint 1 | `skill-creator` |
| ~~8~~ | ~~Chatbot widget site~~ — **cancelled par [D-019](DECISIONS.md#d-019--abandon-d%C3%A9finitif-du-chatbot-widget-site-p8-cancelled)** (2026-05-12) | — | — |
| 9 | ContentBot multi-canal | Sprint 2 | `skill-creator` |
| 10 | SEOBot stratégie + briefs | Sprint 2 | `skill-creator` |
| 11 | Connecteurs sociaux (LinkedIn / Mastodon) | Sprint 2 | — |
| 12 | AdBot — pilotage Google/Meta/LinkedIn Ads | Sprint 3 | `skill-creator` |
| 13 | OutboundBot — cold email volume modéré | Sprint 3 | `skill-creator` |
| 14 | Agent-juge Tier 1 (supervision IA) | Sprint 4 | `skill-creator` |
| 15 | Circuit breakers et kill switches | Sprint 4 | — |
| 16 | Admin Control Panel (start/stop agents, throttle, KPIs, KB editor) | Sprints 1→4 (phasé) | `ui-ux-pro-max` + `frontend-design` (obligatoires) |
| 17 | Conformité RGPD / AI Act / Bloctel | Continu | — |
| 18 | Inventaire des skills à créer | Continu | `skill-creator` |
| 19 | Maintenance et observabilité | Continu | — |
| 20 | Argos Memory (mémoire vivante partagée multi-agents) | Sprint 2+ (prérequis ContentBot/OutboundBot/AdBot live) | — |
| 21 | Paramétrage inter-agents (capabilities pull-based) | Sprint 2+ (après P20) | — |

---

## Légende

- 🎯 **Objectif** — ce que la partie cherche à produire
- 🧱 **Prérequis** — parties à compléter avant
- 📦 **Livrable** — fichiers / services concrets à la fin
- 🛠️ **Skills à utiliser** — quand invoquer `skill-creator`, `frontend-design`, etc.
- ✅ **Done quand** — critères de validation

---

# Partie 0 — Vision et décisions préalables

🎯 **Objectif** : poser le cadre stratégique avant tout code.

## 0.1 Vision produit du système Argos Ops

L'objectif n'est pas de remplacer le fondateur, mais de **lui rendre du temps** :
- Acquisition automatisée (content + SEO + ads + outbound)
- Conversion semi-auto (formulaire contact + email + démo) — pas de chatbot live (D-019)
- Support 24/7 sans humain (Tier 0-1) avec escalade asynchrone (Tier 2)
- Admin financière auto (Stripe + relances + reporting)
- Le fondateur ne touche que le Tier 4 (cas critiques rares) et la stratégie

## 0.2 Architecture en 4 couches

```
┌─────────────────────────────────────────────────────────┐
│  CRM + Knowledge Base central (Postgres + pgvector)     │
└─────────────────────────────────────────────────────────┘
                          ▲
        ┌─────────────────┼─────────────────┐
   ACQUISITION       CONVERSION         RÉTENTION
   (top funnel)      (mid funnel)       (bottom funnel)
   ContentBot        EmailBot in         SupportBot
   SEOBot            DemoBot (P2)        CSMBot
   AdBot             CallerBot (P2)      FinanceBot
   OutboundBot                           AnalyticsBot
```

## 0.3 Système d'escalade Tier 0-4

| Tier | Acteur | Volume cible |
|------|--------|--------------|
| 0 | Agent répond directement | 90 % |
| 1 | Agent-juge IA valide la réponse | 8 % |
| 2 | File asynchrone, fondateur lit 2×/jour, SLA 24 h | 1.5 % |
| 3 | VA externe (Upwork ~5 €/h) si volume dépasse | 0.4 % |
| 4 | Fondateur en synchrone, vrais P0 | 0.1 % |

## 0.4 Décisions figées (réponses fondateur 2026-05-07)

| # | Décision | Choix | Rationale |
|---|----------|-------|-----------|
| 1 | **Hébergement** | ✅ **Couche données** (Postgres / Redis / webhook receivers) sur serveur SecHunter (`204.168.171.71`). **Couche calcul** (agents IA, cron, embeddings) sur **ordi du fondateur** (D-001 partiellement révisé par D-017). | Pas de coût additionnel. Caddy déjà en place pour ajouter `ops.omnividens.fr`. Postgres + Redis déjà actifs. Les agents IA tournent localement via Claude Code Pro Max → 0 API LLM tierce. Trade-off accepté : agents en pause quand l'ordi est éteint (D-017). |
| 2 | **Postgres** | ✅ Nouvelle DB `argos_ops` sur le cluster existant, schémas séparés | 0 coût supplémentaire, isolation logique propre, backups indépendants via `pg_dump argos_ops`. |
| 3 | **Sprint prioritaire** | ✅ Sprint 1 (inbound + finance) | (a) Gain de temps dès J+7 sur les emails / tickets / facturation, (b) la KB construite pour SupportBot sert directement à ContentBot/SEOBot du Sprint 2 ensuite, (c) risque visibilité minimal (back-office privé), permet de valider la mécanique avant d'exposer en public. |
| 4 | **Budget pub initial** | ⏳ À déterminer avant Partie 12 | Pas bloquant pour Sprint 1. AdBot démarrera en shadow mode (analyse sans dépense). Décision à prendre une fois Sprint 1 stable. |
| 5 | **Email public `contact@omnividens.fr`** | ⏳ À vérifier avant Partie 5 | Si pas créé, le faire à ce moment-là. Pas bloquant pour Parties 0-4. |

✅ **Done quand** : les décisions 1-3 figées (fait le 2026-05-07), 4-5 à figer à leur Partie
respective. Réinscrire l'ensemble dans `argos-ops/docs/DECISIONS.md` une fois le bootstrap
fait (Partie 2).

## 0.5 Implications immédiates des choix

- **Caddy** existant doit être étendu pour router `ops.omnividens.fr` → `127.0.0.1:9000`
  (Ops Dashboard, Partie 16). Ce bloc Caddy est à ajouter dans le container
  `sechunter-caddy-1`. (Le sous-domaine `chat.omnividens.fr` initialement prévu
  pour la Partie 8 n'est plus utilisé — cf. [D-019](DECISIONS.md#d-019--abandon-d%C3%A9finitif-du-chatbot-widget-site-p8-cancelled).)
- **Postgres** : `CREATE DATABASE argos_ops OWNER argos_ops;` + user dédié + extension
  pgvector (`CREATE EXTENSION vector;` dans la nouvelle DB). Pas de partage de données
  avec `sechunter` — toute donnée nécessaire (clients, MRR Stripe…) sera répliquée par
  les agents via API Stripe en source de vérité.
- **Redis** : index 3 réservé à Argos Ops (`REDIS_URL=redis://localhost:6379/3`),
  SecHunter utilise déjà 0-2.
- **Cron** : tourne sur **l'ordi du fondateur** (D-017), pas sur le serveur. Windows
  Task Scheduler ou cron WSL2 invoque `claude --print "/<slash-command>"` selon la cadence
  de chaque agent. L'abonnement Claude Code Pro Max du fondateur fournit le runtime IA
  → aucune API LLM tierce facturée pour Argos Ops.
- **GitHub** : nouveau repo privé `omnividens/argos-ops` (séparé de SecHunter) — clean
  pour l'historique et les permissions.

---

# Partie 1 — Préparation technique et choix d'hébergement

🎯 **Objectif** : préparer le terrain technique avant de créer le projet.

🧱 **Prérequis** : Partie 0 validée.

## 1.1 Stack figée

> **Stack v2 — figée par [D-017](DECISIONS.md#d-017--argos-ops-100--local-first--claude-code-pro-max--embeddings-open-source-z%C3%A9ro-api-llm-tierce)** :
> tout LLM passe par Claude Code Pro Max sur l'ordi du fondateur, embeddings
> via modèle local open-source. Aucune API LLM tierce.

| Couche | Technologie | Coût | Hébergement |
|--------|-------------|------|------|
| Runtime de pensée | Claude Code Pro/Max via cron / Task Scheduler | déjà payé | **ordi fondateur** |
| Orchestration | cron / Windows Task Scheduler + scripts Python | 0 € | ordi fondateur |
| CRM | PostgreSQL + pgvector (extension) | 0 € (DB existante) | serveur SecHunter |
| Cache + queue | Redis (cache + idempotency keys agents) | 0 € | serveur SecHunter |
| **LLM agents (tous)** | **Claude Code Pro Max via slash commands** (D-017) | **0 € (forfait Pro Max)** | runtime ordi |
| **Embeddings KB** | **`fastembed` + `multilingual-e5-base`** (CPU local) (D-017) | **0 € forever** | ordi fondateur |
| Email inbound | Gmail API + IMAP | 0 € | runtime ordi |
| Email outbound (volume modéré) | Gmail API (≤ 500/jour) | 0 € | runtime ordi |
| Social posting | API natives LinkedIn / Mastodon (D-004 remplace X, D-022 retire Reddit) | 0 € | runtime ordi |
| Ads pilotage | Google Ads / Meta / LinkedIn Marketing APIs | 0 € (budget pub à part) | runtime ordi |
| Webhook receivers | FastAPI + Caddy reverse proxy (Stripe webhook, futur) | 0 € | serveur SecHunter |
| Analytics | Umami self-host (D-007 reporte à INFRA-02) | 0 € | serveur SecHunter |
| Téléphonie IA | reporté en phase 2 | — | — |
| Avatar démo | reporté en phase 2 | — | — |

## 1.2 Variables d'environnement à provisionner

À mettre dans un futur `argos-ops/.env` (généré en Partie 2) :

```
DATABASE_URL=postgresql://argos_ops:***@localhost:5432/argos_ops
REDIS_URL=redis://localhost:6379/3
# GEMINI_API_KEY — DÉPRÉCIÉ pour Argos Ops (D-017). Reste optionnel
# uniquement pour le scanner SecHunter BYOK (D-011), produit séparé.
LINKEDIN_CLIENT_ID=
LINKEDIN_CLIENT_SECRET=
LINKEDIN_ACCESS_TOKEN=
MASTODON_INSTANCE_URL=            # D-004 remplace X par Mastodon
MASTODON_ACCESS_TOKEN=
REDDIT_CLIENT_ID=
REDDIT_CLIENT_SECRET=
GMAIL_CLIENT_ID=
GMAIL_CLIENT_SECRET=
GMAIL_REFRESH_TOKEN=
STRIPE_SECRET_KEY=                # déjà en prod SecHunter, à factoriser
GOOGLE_ADS_DEVELOPER_TOKEN=
META_ADS_ACCESS_TOKEN=
DISCORD_WEBHOOK_URL=              # pour digest fondateur
ARGOS_OPS_LOG_LEVEL=INFO
```

> **Note D-017** : aucune clé d'API LLM n'est requise pour Argos Ops.
> Tous les agents IA passent par Claude Code Pro Max (abonnement
> fondateur), les embeddings KB par `fastembed` local. Le seul composant
> IA qui nécessitait une clé Gemini (le seed KB initial + le chat live)
> est désormais 100 % local.

## 1.3 Comptes à créer (gratuit)

- **Discord** : serveur perso + 1 webhook par canal d'escalade — 10 min
- **Mastodon** : compte `infosec.exchange` + token API — 10 min (D-004 remplace X)
- **LinkedIn Developer** : 2 apps (D-006) — 1 h (le plus long)
- ~~**Google AI Studio** (Gemini key)~~ — **non nécessaire pour Argos Ops** (D-017).
  Optionnel uniquement pour le scanner SecHunter BYOK.
- ~~**Plausible self-host**~~ — **reporté à INFRA-02** (D-007 / Umami)

✅ **Done quand** les comptes sont créés, les clés stockées dans un gestionnaire (1Password,
Bitwarden, ou fichier chiffré local), le `.env.example` listé ci-dessus est rédigé.

---

# Partie 2 — Bootstrap du dossier `argos-ops`

🎯 **Objectif** : créer le squelette projet, init git, premier push GitHub privé.

🧱 **Prérequis** : Partie 1 — au minimum hébergement et DB choisis.

📦 **Livrable** : dossier complet `~/Desktop/argos-ops/` versionné Git.

## 2.1 Arborescence cible

```
argos-ops/
├── .claude/
│   ├── commands/                       # slash commands = un par agent
│   ├── skills/                         # skills réutilisables
│   ├── agents/                         # subagents spécialisés
│   └── settings.json                   # permissions + hooks
├── argos_ops/
│   ├── __init__.py
│   ├── crm/                            # modèles + repo CRM
│   │   ├── __init__.py
│   │   ├── models.py
│   │   ├── migrations/
│   │   └── repository.py
│   ├── integrations/                   # un module par API externe
│   │   ├── __init__.py
│   │   ├── linkedin.py
│   │   ├── mastodon.py                # D-004 remplace twitter
│   │   ├── gmail.py
│   │   ├── stripe.py
│   │   ├── embeddings.py              # D-017 — fastembed multilingual-e5-base local
│   │   ├── google_ads.py
│   │   ├── meta_ads.py
│   │   └── umami.py                   # D-007 (analytics, INFRA-02)
│   └── ops_dashboard/
│       └── app.py
├── docs/
│   ├── ARCHITECTURE.md
│   ├── AGENTS_PLAYBOOK.md
│   ├── ESCALATION_RULES.md
│   ├── DECISIONS.md                    # décisions Partie 0
│   └── COMPLIANCE.md                   # règles RGPD / AI Act / Bloctel
├── data/
│   ├── knowledge_base/                 # markdown indexé en pgvector
│   │   ├── argos_features.md
│   │   ├── pricing.md
│   │   ├── faq.md
│   │   ├── tone_of_voice.md
│   │   ├── competitor_compare.md
│   │   └── ICP.md                      # Ideal Customer Profile
│   └── prompts/
├── scripts/
│   ├── install_cron.sh
│   ├── seed_kb.py
│   └── health_check.py
├── tests/
├── pyproject.toml
├── .env.example
├── .gitignore
├── CLAUDE.md                           # instructions projet
└── README.md
```

## 2.2 `pyproject.toml` minimal

Dépendances à figer dès le bootstrap (ajouts en cours de route possibles) :

```toml
[project]
name = "argos-ops"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
  "httpx[http2]>=0.27",
  "pydantic>=2.7",
  "sqlmodel>=0.0.16",
  "psycopg[binary]>=3.1",
  "pgvector>=0.2.5",
  "redis>=5.0",
  "loguru>=0.7",
  "fastapi>=0.110",
  "uvicorn>=0.29",
  "fastembed>=0.3",                     # Embeddings KB local (D-017)
  "google-auth>=2.29",
  "google-auth-oauthlib>=1.2",
  "google-api-python-client>=2.125",   # Gmail
  "Mastodon.py>=1.8",                   # D-004 remplace tweepy/X
  "linkedin-api-client>=0.3",
  "stripe>=9.5",
  "python-dotenv>=1.0",
]

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.mypy]
strict = true
```

## 2.3 `CLAUDE.md` du projet (squelette)

Le fichier doit contenir :
- Vision (1 paragraphe)
- Règles de commit / PR (mêmes que SecHunter : branche par feature, pas de push direct main)
- Liste des slash commands disponibles à mesure qu'ils sont créés
- Liste des skills locaux à mesure qu'ils sont créés
- État d'avancement (Sprint courant / parties faites)
- Pointeurs vers `docs/AGENTS_PLAYBOOK.md`, `docs/ESCALATION_RULES.md`, `docs/COMPLIANCE.md`

## 2.4 Init Git + GitHub

1. `git init`, `.gitignore` standard Python + `.env`
2. Créer repo GitHub privé `omnividens/argos-ops`
3. Premier commit : « chore: bootstrap argos-ops skeleton »
4. Brancher CI minimal (lint + tests) — peut être ajouté en Partie 19

✅ **Done quand** : `argos-ops/` existe, premier commit poussé, `pyproject.toml` valide
(`uv sync` fonctionne), `CLAUDE.md` rédigé, `docs/DECISIONS.md` rempli avec les 5 réponses
de la Partie 0.

---

# Partie 3 — Schéma CRM + Knowledge Base

🎯 **Objectif** : poser la donnée centrale dans laquelle tous les agents lisent et écrivent.

🧱 **Prérequis** : Partie 2.

📦 **Livrables** :
- Migration SQL initiale dans `argos_ops/crm/migrations/0001_init.sql`
- Modèles SQLModel dans `argos_ops/crm/models.py`
- Repository fonctionnel dans `argos_ops/crm/repository.py`
- Knowledge base markdown peuplée à la main dans `data/knowledge_base/`
- Script `scripts/seed_kb.py` qui chunk + embed + insère dans pgvector

## 3.1 Tables CRM minimales

```sql
-- Identités
CREATE TABLE companies (
  id BIGSERIAL PRIMARY KEY,
  domain TEXT UNIQUE,
  name TEXT,
  industry TEXT,
  size_band TEXT,
  source TEXT,                    -- 'inbound_chat' | 'outbound' | 'ad_lead'
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE leads (
  id BIGSERIAL PRIMARY KEY,
  company_id BIGINT REFERENCES companies(id),
  email TEXT UNIQUE,
  full_name TEXT,
  job_title TEXT,
  linkedin_url TEXT,
  phone TEXT,
  status TEXT,                    -- 'new' | 'qualified' | 'demo_booked' | 'customer' | 'lost'
  bant_score INT,                 -- 0-100
  consent_email BOOLEAN DEFAULT false,
  consent_phone BOOLEAN DEFAULT false,
  bloctel_checked_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE interactions (
  id BIGSERIAL PRIMARY KEY,
  lead_id BIGINT REFERENCES leads(id),
  channel TEXT,                   -- 'email' | 'chat' | 'phone' | 'linkedin' | 'x'
  direction TEXT,                 -- 'in' | 'out'
  agent_name TEXT,                -- 'EmailBot' | 'SupportBot' | 'FinanceBot' | ...
  subject TEXT,
  body TEXT,
  judge_score INT,                -- 0-100, NULL si non jugé
  judge_verdict TEXT,             -- 'auto_send' | 'queued' | 'killed'
  occurred_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE tickets (
  id BIGSERIAL PRIMARY KEY,
  lead_id BIGINT REFERENCES leads(id),
  status TEXT,                    -- 'open' | 'pending_human' | 'closed'
  priority TEXT,                  -- 'P0' | 'P1' | 'P2'
  summary TEXT,
  resolution TEXT,
  opened_at TIMESTAMPTZ DEFAULT now(),
  closed_at TIMESTAMPTZ
);

-- Observabilité agents
CREATE TABLE agent_runs (
  id BIGSERIAL PRIMARY KEY,
  agent_name TEXT,
  command TEXT,
  started_at TIMESTAMPTZ DEFAULT now(),
  ended_at TIMESTAMPTZ,
  status TEXT,                    -- 'success' | 'failed' | 'killed_by_breaker'
  output_summary TEXT,
  error TEXT,
  cost_estimate_eur NUMERIC(10,4)
);

-- Knowledge Base vectorielle
CREATE EXTENSION IF NOT EXISTS vector;
CREATE TABLE kb_chunks (
  id BIGSERIAL PRIMARY KEY,
  doc_path TEXT,                  -- 'data/knowledge_base/pricing.md'
  chunk_index INT,
  content TEXT,
  embedding vector(768),          -- multilingual-e5-base local = 768 dims natif (D-017)
  updated_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX ON kb_chunks USING ivfflat (embedding vector_cosine_ops);

-- Circuit breakers state
CREATE TABLE breakers (
  name TEXT PRIMARY KEY,
  tripped BOOLEAN DEFAULT false,
  tripped_at TIMESTAMPTZ,
  reason TEXT,
  reset_after TIMESTAMPTZ
);

-- Configuration runtime des agents (pilotée par l'Admin Control Panel, P16)
CREATE TABLE agent_config (
  agent_name TEXT PRIMARY KEY,        -- 'ContentBot', 'EmailBot', 'AdBot', ...
  enabled BOOLEAN DEFAULT true,
  intensity_level INT DEFAULT 5,      -- 1 (très éco) à 10 (à fond)
  schedule_cron TEXT,                 -- '*/15 * * * *' éditable depuis le dashboard
  daily_limit INT,                    -- volume max d'actions par jour (NULL = pas de limite)
  max_tokens_per_day INT,             -- quota LLM par jour (NULL = pas de limite)
  tier1_threshold INT DEFAULT 80,     -- seuil agent-juge pour auto-send (50-100)
  paused_until TIMESTAMPTZ,           -- pause temporaire (1h, 24h, manuelle)
  notes TEXT,                         -- raison d'un état exceptionnel
  updated_at TIMESTAMPTZ DEFAULT now(),
  updated_by TEXT                     -- 'system' | 'admin' | nom du breaker
);

-- Sessions d'authentification du Admin Control Panel
CREATE TABLE admin_sessions (
  token TEXT PRIMARY KEY,
  created_at TIMESTAMPTZ DEFAULT now(),
  expires_at TIMESTAMPTZ NOT NULL,
  ip_address TEXT,
  user_agent TEXT,
  revoked BOOLEAN DEFAULT false
);
```

## 3.2 Knowledge Base (à rédiger à la main)

Le fondateur écrit ces fichiers (Claude peut aider mais il faut la voix authentique) :

| Fichier | Contenu |
|---------|---------|
| `argos_features.md` | Liste exhaustive des 130 modules v2, par catégorie, avec ce que chacun trouve |
| `pricing.md` | Free / Pro 30 € / Pro Max 70 € — plans, limites, comparatif |
| `faq.md` | 30-50 Q&R récurrentes (BYOK, conformité, intégration CI/CD, support, etc.) |
| `tone_of_voice.md` | Vocabulaire, ton, formules à éviter, exemples avant/après |
| `competitor_compare.md` | Argos vs Acunetix vs Burp vs Detectify vs Pentera (forces, faiblesses) |
| `ICP.md` | Ideal Customer Profile : RSSI / DevSecOps / CTO PME-ETI FR/EU, signaux d'achat |

## 3.3 Script `seed_kb.py`

- Lit chaque `.md` dans `data/knowledge_base/`
- Chunk par section H2 ou bloc de 800 tokens max avec overlap 100
- Embed via `fastembed` + `intfloat/multilingual-e5-base` (CPU local, 0 € forever — D-017)
- Upsert dans `kb_chunks` avec `(doc_path, chunk_index)` comme clé naturelle
- Idempotent : si le hash du chunk n'a pas changé, skip

✅ **Done quand** : migration appliquée, 6 fichiers KB peuplés, `python scripts/seed_kb.py`
crée ≥ 50 chunks dans `kb_chunks`, requête de similarité sur « combien coûte Pro Max »
retourne le bon chunk de `pricing.md`.

---

# Partie 4 — Premier slash command — `/morning-digest`

🎯 **Objectif** : valider la chaîne « cron → Claude Code → action → log DB » avec
l'agent le plus simple : un digest quotidien envoyé sur Discord.

🧱 **Prérequis** : Parties 2 et 3.

📦 **Livrables** :
- `.claude/commands/morning-digest.md`
- Skill `digest-builder` (optionnel mais recommandé)
- Entrée cron `0 8 * * * cd ~/argos-ops && claude --print "/morning-digest"`
- Log d'exécution dans `agent_runs`

🛠️ **Skills à utiliser** : invoquer le skill `skill-creator` à cette étape pour formaliser
le skill `digest-builder` qui sera ensuite réutilisable par AnalyticsBot. Le skill encapsule
la logique « lire les KPIs des dernières 24 h dans Postgres + Stripe + Plausible et formater
en markdown court ».

## 4.1 Contenu attendu du digest

Sur Discord chaque matin 8 h :

```
📊 Argos — Digest 2026-MM-DD

MRR : 1 234 € (+5 % vs semaine -1)
Leads J-1 : 12 (8 chat / 3 email / 1 outbound)
Conversions : 1 nouveau client (Pro 30 €)
CAC blended J-1 : 0 € (pas de pub)

⚠️ Escalades en attente : 2 emails, 1 ticket P1
🚦 Breakers actifs : aucun
```

## 4.2 Algorithme du slash command

1. Charger les KPIs depuis Postgres (`leads`, `interactions`, `tickets`, Stripe API)
2. Composer le digest via Claude (le slash command est lui-même le prompt)
3. Poster sur Discord via webhook
4. Logger dans `agent_runs`

✅ **Done quand** : un cron lancé manuellement produit un digest valide sur Discord, et la
ligne correspondante apparaît dans `agent_runs` avec `status='success'`.

---

# Partie 5 — EmailBot inbound

🎯 **Objectif** : ingester les emails de `contact@omnividens.fr` toutes les 15 min,
les logger dans le CRM, notifier Discord. La rédaction des réponses se fait
ensuite via le slash command `/check-emails` (Claude Code Pro Max + skills).

> **Stack ré-alignée par D-018** : OVH Zimbra IMAP/SMTP (pas Gmail Workspace,
> pas self-host). Boîte canonique `contact@omnividens.fr`, hôte `ssl0.ovh.net`,
> ports `993` (IMAP SSL) / `465` (SMTP SSL).
>
> **Inférence ré-alignée par D-017** : aucun appel LLM tiers depuis le code
> Python. La cron pull + log + notifie. La classification fine + le drafting
> RAG se font dans Claude Code via le slash command `/check-emails` quand
> l'opérateur ouvre la session.

🧱 **Prérequis** : Parties 2, 3, 4. Compte OVH `contact@omnividens.fr`
opérationnel (D-005 finalisé).

📦 **Livrables** :
- `argos_ops/integrations/zimbra.py` — wrapper IMAP/SMTP async (fetch_unread,
  mark_seen, send_email)
- `argos_ops/agents/email_bot.py` — `EmailBot(BaseAgent)` qui pull + log + notif
- `scripts/run_email_bot.py` — entrée CLI invoquée par cron / Task Scheduler
- `.claude/commands/check-emails.md` — slash command pour drafting humain-in-the-loop
- Skill `zimbra-ops` (lire, drafter, envoyer, marquer lu — utilisé par
  `/check-emails`, OutboundBot P13, FinanceBot P7)
- Skill `email-classifier` (classifie en `lead_chaud` / `question_tech` /
  `sav` / `spam` — Claude inline, pas d'API)
- Schedule cron `*/15 * * * *` (Paris) dans Task Scheduler Windows

🛠️ **Skills à utiliser** :
- `skill-creator` pour formaliser `zimbra-ops` (réutilisable par OutboundBot)
- `skill-creator` pour formaliser `email-classifier`

## 5.1 Pipeline (cron `*/15`)

```
Boîte IMAP OVH Zimbra (contact@omnividens.fr)
     ↓
1. Connexion IMAP SSL ssl0.ovh.net:993
     ↓
2. Pull UIDs INBOX où SEEN=False
     ↓
3. Pour chaque email :
   - Skip si expéditeur contient noreply@ / mailer-daemon / bounces
   - Lookup company par domaine, créer si absent
   - Lookup lead par email, créer si absent
   - Insert interaction(channel='email', direction='in', body=message)
   - IMAP STORE +FLAGS \Seen
     ↓
4. Notif Discord (webhook escalations) :
   « N emails reçus, M nouveaux leads. Lance /check-emails pour drafter. »
     ↓
5. Insert agent_runs(status='success', summary=...)
```

## 5.2 Pipeline (slash command `/check-emails`, opérateur)

```
Opérateur ouvre Claude Code → /check-emails
     ↓
1. Lit interactions(channel='email', direction='in', sans réponse out liée)
     ↓
2. Pour chaque email non répondu :
   - Skill email-classifier → tag (lead_chaud / question_tech / sav / spam)
   - Skill kb-rag (P6+) → top-3 chunks pertinents
   - Drafte une réponse personnalisée
   - Soumet pour validation à l'opérateur (humain-in-the-loop)
     ↓
3. Sur validation : skill zimbra-ops envoie via SMTP SSL ssl0.ovh.net:465
   - Insert interaction(direction='out', judge_verdict='human_validated')
4. Sur rejet : log + skip (l'opérateur peut écrire à la main)
```

L'agent-juge Tier 1 (Partie 14) viendra s'intercaler plus tard pour passer
en envoi auto sans validation humaine pour les cas Tier 0/1.

## 5.3 Garde-fous

- Ne jamais répondre à un email avec `noreply@` / `mailer-daemon` / `bounces`
  dans l'expéditeur (filtre côté EmailBot, pas côté slash command)
- Détecter les boucles (3 emails échangés en moins de 5 min → flag dans
  l'interaction, l'opérateur tranche)
- Pas de limite warm-up tant que l'envoi est validé humain (P5). Limite
  reviendra avec l'agent-juge auto (P14) : 50 réponses auto/jour pendant 1 mois

## 5.4 Variables `.env.local`

```
EMAIL_IMAP_HOST=ssl0.ovh.net
EMAIL_IMAP_PORT=993
EMAIL_SMTP_HOST=ssl0.ovh.net
EMAIL_SMTP_PORT=465
EMAIL_USER=contact@omnividens.fr
EMAIL_PASSWORD=...        # mot de passe Zimbra OVH (pas le mot de passe du compte OVH)
EMAIL_REPLY_NAME=Argos par Omnividens
DISCORD_WEBHOOK_INBOX=... # optionnel, fallback sur DISCORD_WEBHOOK_ESCALATIONS
```

✅ **Done quand** :
- un email envoyé à `contact@omnividens.fr` est ingéré dans `interactions` en
  moins de 20 min, lead + company créés si nouveaux, IMAP \Seen positionné
- une notif Discord push avec le compte d'emails ingérés
- une ligne `agent_runs` avec `status='success'`
- `/check-emails` répond proprement quand il n'y a rien à drafter (idempotent)

---

# Partie 6 — SupportBot Tier 1 (RAG sur KB)

🎯 **Objectif** : répondre aux tickets simples (questions sur features, pricing, intégration)
en s'appuyant sur la KB pgvector.

🧱 **Prérequis** : Parties 3, 5.

📦 **Livrables** :
- `.claude/commands/run-support-tier1.md`
- Skill `kb-rag` (recherche similarité + assemblage contexte)
- Intégration EmailBot consomme ce skill via `/check-emails`

🛠️ **Skills à utiliser** :
- `skill-creator` pour `kb-rag` (réutilisable par EmailBot, ContentBot, OutboundBot)

## 6.1 Pipeline RAG

1. Question entrante (texte brut)
2. Embed via `fastembed` + `multilingual-e5-base` local (D-017)
3. Top-K = 5 chunks via similarité cosinus dans `kb_chunks`
4. Assembler contexte avec citation des `doc_path` source
5. Demander à Claude de répondre EN CITANT les sources
6. Si Claude indique "je ne sais pas" ou confiance basse → escalade Tier 2

## 6.2 Garde-fou hallucination

Le prompt système impose explicitement :
- « Réponds UNIQUEMENT à partir des extraits fournis. »
- « Si la question n'est pas couverte, dis-le et propose une escalade. »
- L'agent-juge (Partie 14) vérifie ensuite que les claims de la réponse sont bien
  présents dans les chunks fournis (anti-hallucination).

✅ **Done quand** : 10 questions de test (5 dans la KB, 5 hors KB) donnent 10 verdicts
corrects (5 réponses + 5 escalades).

---

# Partie 7 — FinanceBot (Stripe + relances)

🎯 **Objectif** : facturation, relances impayés, MRR, alertes anomalie.

🧱 **Prérequis** : Parties 2, 3, 4.

📦 **Livrables** :
- `.claude/commands/daily-finance-sync.md`
- Skill `stripe-ops` (lire factures, status, relance, webhooks)
- Routine quotidienne 6 h

🛠️ **Skills à utiliser** :
- `skill-creator` pour `stripe-ops`

## 7.1 Tâches journalières

- Pull abonnements Stripe → mettre à jour `companies.status`
- Détecter impayés J+3, J+7, J+15 → email de relance auto avec ton dégradé
- Calculer MRR / NRR / churn → écrire dans `agent_runs.output_summary` pour le digest
- Alerte Discord si MRR baisse > 5 % sur 7 jours
- Génération facture conforme FR (TVA, mentions légales) — déjà gérée par Stripe Tax si
  activé, sinon helper Python

## 7.2 Conformité

- Mentions obligatoires sur factures FR : SIREN, TVA intracommunautaire, conditions de
  paiement, taux de pénalité de retard, indemnité forfaitaire 40 €.
- Documenter dans `docs/COMPLIANCE.md` (Partie 17).

✅ **Done quand** : un run produit un rapport MRR/NRR exact à ±1 € près sur la période, les
relances impayées sont déclenchées automatiquement à J+3.

---

# Partie 8 — Chatbot widget site — ❌ CANCELLED (D-019)

> **Statut : annulée le 2026-05-12** par
> [D-019](DECISIONS.md#d-019--abandon-d%C3%A9finitif-du-chatbot-widget-site-p8-cancelled).
> Argos Ops n'aura pas de chatbot widget sur `omnividens.fr`. Le canal entrant
> reste **email exclusivement** (`contact@omnividens.fr`, EmailBot P5 +
> SupportBot P6 + `/check-emails` humain-validé).

**Pourquoi (résumé)** :
- Latence pull-based Claude Code Pro Max (D-017) incompatible avec UX chat
  temps-réel (visiteur attendrait 1-5 min en heures ouvrées, hors heures ouvrées
  jusqu'au réveil de l'ordi du fondateur).
- Surface fonctionnelle déjà couverte par EmailBot P5 + formulaire contact
  HTML (à brancher côté repo SecHunter, mailto `contact@omnividens.fr`).
- Compliance RGPD / AI Act simplifiée : pas de bandeau IA chat, pas de cookie
  de session, pas de retention 1 an de conversations.

Cf. [D-019](DECISIONS.md#d-019--abandon-d%C3%A9finitif-du-chatbot-widget-site-p8-cancelled)
pour les détails complets (alternatives écartées, scope du cleanup, conditions
de réversibilité future).

**Implication sur le plan** :
- Sprint 1 ne contient plus que P5 / P6 / P7 (clos officiellement 2026-05-12).
- Sous-domaine `chat.omnividens.fr` non provisionné.
- Skill `chat-orchestrator` retiré de l'inventaire P18.
- KPI « Latence p95 ChatBot » retiré de § 19.3.

---

# Partie 9 — ContentBot multi-canal

🎯 **Objectif** : 2-5 posts/jour sur LinkedIn / Mastodon (D-022 retire Reddit), ton
adapté à chaque plateforme, sujets pilotés par SEOBot (Partie 10).

🧱 **Prérequis** : Parties 3, 11 (connecteurs sociaux).

> **MàJ 2026-06-01** : le skill `content-writer` multi-canal a été
> **scindé en skills dédiés par canal** — `linkedin-writer`,
> `mastodon-writer`, `bluesky-writer` (cf. Annexe D). Lire « skill du canal »
> partout où ce § dit « content-writer ».

📦 **Livrables** :
- `.claude/commands/run-content-bot.md`
- Skills par canal `linkedin-writer` / `mastodon-writer` / `bluesky-writer`
  (génèrent le contenu adapté à leur canal ; ex-`content-writer` déprécié)
- Skill `content-scheduler` (poste à l'heure optimale par canal)

🛠️ **Skills à utiliser** :
- `skill-creator` pour chaque writer de canal (`linkedin-writer`,
  `mastodon-writer`, `bluesky-writer`)
- `skill-creator` pour `content-scheduler`

## 9.1 Logique quotidienne

1. Lire le calendrier éditorial dans une nouvelle table `editorial_calendar`
   (rempli par SEOBot la veille)
2. Pour chaque slot du jour :
   - Choisir le canal (LinkedIn / Mastodon infosec / Bluesky)
   - Générer le post via le skill du canal (`linkedin-writer` /
     `mastodon-writer` / `bluesky-writer`) avec ses contraintes
     (LinkedIn 1300-2000 chars, Mastodon 300-500, Bluesky ≤300 graphemes)
   - Soumettre à l'agent-juge Tier 1
   - Publier via skill `content-scheduler` à l'heure optimale par canal
3. Logger dans `interactions` avec `agent_name='ContentBot'`

## 9.2 Particularités par canal

- **LinkedIn** : algo punit > 5 hashtags. Pas de markdown bold/italic.
  Refresh token long-lived requis (Marketing Developer Platform si volume).
- **Mastodon** : instance `infosec.exchange` impose bot flag activé sur
  le compte. Pas de promo directe — partage technique d'abord. Audience
  tech crowd, vocabulaire technique acceptable.

✅ **Done quand** : 5 posts publiés sur 24 h sur 2 canaux, engagement
loggé dans `interactions.judge_score` (récupération likes/comments J+1).

---

# Partie 10 — SEOBot (stratégie + briefs)

🎯 **Objectif** : analyser SERP concurrents, identifier keyword gaps, produire 1-2 briefs
de blog par semaine que ContentBot exécute.

🧱 **Prérequis** : Parties 3, 9.

📦 **Livrables** :
- `.claude/commands/run-seo-bot.md` (hebdo, lundi 6 h)
- Skill `serp-analyzer` (scrape Google SERP via DataForSEO free trial ou ScrapingBee
  free OU scraping direct avec rotation User-Agent)
- Articles publiés sur le blog (Ghost ou WordPress headless du site existant)

🛠️ **Skills à utiliser** :
- `skill-creator` pour `serp-analyzer`

## 10.1 Stratégie keywords

- Cible : 200-500 keywords longue traîne BtoB cybersécurité FR/EN
- Sources gratuites : Google Search Console (déjà branché ?), Google Suggest, AnswerThePublic
  free, Hacker News commentaires (r/netsec retiré D-022), KeywordTool free
- Score = volume × intention transactionnelle / difficulté

## 10.2 Output

Brief = markdown avec :
- Titre H1
- Outline H2/H3
- 5 sources autorité à citer
- 3 internal links vers pages du site
- Meta title + description
- ~2000 mots cible

ContentBot consomme ce brief et publie l'article. Le bot ne réécrit pas tout seul sans brief.

✅ **Done quand** : 1 brief produit le lundi, 1 article publié le vendredi, ranking Google
Search Console suivi semaine + 2.

---

# Partie 11 — Connecteurs sociaux (LinkedIn / Mastodon)

🎯 **Objectif** : modules Python `argos_ops/integrations/` testés, OAuth qui marche,
post & lecture engagement automatisés. **Périmètre réduit à 2 canaux**
(D-004 retire X, D-022 retire Reddit) — LinkedIn + Mastodon uniquement.

🧱 **Prérequis** : Partie 1 (comptes API créés). Mastodon déjà OK
(P11-PREP-B done 2026-05-14, token validé). LinkedIn en attente
d'approbation Community Management API.

📦 **Livrables** :
- `argos_ops/integrations/linkedin.py` (publish, get_engagement, list_posts)
- `argos_ops/integrations/mastodon.py` (idem)
- Tests d'intégration `tests/integrations/` avec cassettes vcrpy

## 11.1 Particularités

- **LinkedIn** : auth la plus complexe, refresh token long-lived, API rate limit strict
  (100 calls/jour pour profil personnel sans Marketing Developer Platform)
- **Mastodon** : token statique (déjà obtenu via `scripts/smoke_mastodon.py`
  2026-05-14), instance `infosec.exchange`, bot flag activé requis,
  rate limit large (300 req / 5 min)

## 11.2 Pas de skill-creator ici

Pure plomberie HTTP, mieux vaut du Python testé que des skills.

✅ **Done quand** : `python -m argos_ops.integrations.linkedin --test-post "hello"`
publie un post test sur le profil et le supprime ensuite. Idem Mastodon.

---

# Partie 12 — AdBot (pilotage Google / Meta / LinkedIn Ads)

🎯 **Objectif** : optimiser les campagnes existantes (créer / pause / budget) selon CTR,
CPA, conversions. Sans budget pub initial, l'agent reste en "shadow mode" et propose
des actions sans les exécuter.

🧱 **Prérequis** : Parties 3, 14 (judge), 15 (breakers).

📦 **Livrables** :
- `.claude/commands/run-ad-bot.md` (toutes les 4 h en heures ouvrées)
- Skill `ads-optimizer` (analyse perf, propose actions)
- Skill `ads-creative-writer` (génère 3 variantes ads/jour)

🛠️ **Skills à utiliser** :
- `skill-creator` pour `ads-optimizer`
- `skill-creator` pour `ads-creative-writer`

## 12.1 Modes de fonctionnement

- **Shadow mode** (défaut, budget = 0) : analyse uniquement, écrit ses recommandations
  dans Discord, pas d'action. Permet de valider la qualité de l'agent avant de lui
  confier de l'argent.
- **Live mode** (budget > 0) : applique automatiquement avec hard caps :
  - Pause auto si CPA > 2× cible sur 24 h
  - Pas de hausse de budget journalier > +10 %/jour
  - Alerte si dépense quotidienne > 1.5× budget cible

## 12.2 Garde-fous via circuit breakers

Voir Partie 15 — breaker `ad_spend_runaway` qui kill toute campagne si dépense > seuil
sur 24 h.

✅ **Done quand** : en shadow mode, 1 recommandation/jour sur Discord avec rationale
chiffré (CTR, CPA, conv rate). Test live sur 50 € de budget pendant 1 semaine valide le
mode auto avant de scaler.

---

# Partie 13 — OutboundBot (cold email volume modéré)

🎯 **Objectif** : 30-50 emails/jour vers ICP, séquence 5-touch, opt-out 1-clic, conformité
RGPD (intérêt légitime BtoB).

🧱 **Prérequis** : Parties 3, 5, 14, 15, 17.

📦 **Livrables** :
- `.claude/commands/run-outbound-bot.md` (quotidien 9 h)
- Skill `lead-enricher` (depuis nom + domaine, devine email + titre)
- Skill `outbound-personalizer` (1 ligne hyper-perso par lead)
- Liste seed ICP (CSV manuel pour démarrer, scraping ensuite)

🛠️ **Skills à utiliser** :
- `skill-creator` pour `lead-enricher`
- `skill-creator` pour `outbound-personalizer`

## 13.1 Source des leads

- Démarrage : CSV manuel de 200 leads (LinkedIn search → export). Légal en France
  pour BtoB si l'on a un intérêt légitime documenté + opt-out facile.
- Phase suivante : Apollo free trial (50 leads/mois) ou scraping Google + LinkedIn
  Sales Navigator si le fondateur l'a.

## 13.2 Délivrabilité

- Domaine principal `omnividens.fr` JAMAIS utilisé pour outbound (préserve la réputation)
- Domaine secondaire à acquérir : `try-omnividens.com` ou `hello-omnividens.com` (~10 €/an)
- SPF / DKIM / DMARC stricts sur le secondaire
- Warm-up 4 semaines à 5 emails/jour avant scale à 30
- Volume cible mois 2-3 : 50/jour max via Gmail

## 13.3 Conformité

Voir Partie 17 — opt-out 1-clic via lien `https://omnividens.fr/unsubscribe?token=...`,
table `unsubscribes`, suppression définitive sous 7 jours.

✅ **Done quand** : 10 emails envoyés en J1 sans bounces, 0 spam complaint, 1+ réponse
positive en semaine 2.

---

# Partie 14 — Agent-juge Tier 1 (supervision IA)

🎯 **Objectif** : LLM secondaire qui audite chaque output d'agent avant envoi, score 0-100
sur 3 axes (factuel / ton / risque légal).

🧱 **Prérequis** : Parties 3, 6.

📦 **Livrables** :
- Skill `claude-judge` (le cœur du Tier 1)
- Intégré dans EmailBot, SupportBot, ContentBot, OutboundBot
- Champ `judge_score` et `judge_verdict` rempli partout

🛠️ **Skills à utiliser** :
- `skill-creator` pour `claude-judge` (skill central, le plus important du système)

## 14.1 Prompt système du juge

Le juge reçoit :
- La requête originale (mail entrant, message chat, brief)
- La réponse drafte par l'agent
- Le contexte RAG utilisé (chunks KB)
- Les règles ESCALATION_RULES.md

Il retourne un JSON :

```json
{
  "factual_score": 0-100,        "factual_issues": ["..."],
  "tone_score": 0-100,           "tone_issues": ["..."],
  "legal_score": 0-100,          "legal_issues": ["..."],
  "global_score": 0-100,
  "verdict": "auto_send" | "queued" | "killed",
  "rationale": "..."
}
```

## 14.2 Calibration

- 50 cas test dans `tests/judge/fixtures/` couvrant : bon, médiocre, mensonger,
  ton agressif, info confidentielle, claim non sourcé
- Le juge doit avoir > 90 % d'accord avec le verdict humain sur ce dataset
- Re-calibrer le prompt système quand un faux positif/négatif apparaît en prod

## 14.3 Coût

Le juge double les tokens consommés. Sur Claude Sonnet 4.6 via Claude Code abonnement,
le coût marginal est nul (compris dans l'abonnement). C'est pour ça qu'on peut se le
permettre sur 100 % du trafic sortant.

✅ **Done quand** : 50 cas test passent, le skill est appelé par au moins 2 agents
(EmailBot + SupportBot) en production, et la table `interactions` montre des verdicts
distribués (auto_send / queued / killed dans des proportions cohérentes ~85/13/2 %).

---

# Partie 15 — Circuit breakers et kill switches

🎯 **Objectif** : table `breakers` qui peut couper automatiquement n'importe quel agent
si une métrique dérive.

🧱 **Prérequis** : Partie 3 (table `breakers`).

📦 **Livrables** :
- `argos_ops/breakers.py` — module Python qui expose `check(name)` et `trip(name, reason)`
- Hook Claude Code `PreToolUse` qui consulte les breakers avant chaque action
  d'agent (cf. Partie 19)
- Liste des 10 breakers initiaux ci-dessous

## 15.1 Breakers minimum

| Nom | Trigger | Action |
|-----|---------|--------|
| `ad_spend_runaway` | dépense > 1.5× budget cible / 24 h | pause toutes campagnes, notif fondateur |
| `email_spam_complaints` | > 3 complaints/jour | stop OutboundBot, switch domaine |
| `support_low_confidence` | 3 tickets consécutifs avec judge_score < 60 | désactive auto-réponse, file 100 % en Tier 2 |
| `mrr_drop` | MRR -5 % sur 7 jours | notif P0 fondateur |
| `pro_max_quota` | > 90 % du quota mensuel Claude Pro Max consommé | ralentir cadence cron + alerter fondateur (D-017) |
| `gmail_rate_limit` | > 90 % du quota Gmail | pause sends jusqu'à minuit |
| `outbound_bounce_rate` | > 5 % bounce sur 24 h | pause OutboundBot, audit liste |
| `social_api_error` | 3 errors consécutives | pause canal concerné |
| `judge_disagreement` | > 20 % de queued/jour (vs ~13 % attendu) | alerte qualité, recalibration |
| `daily_cost_estimate` | coût estimé jour > seuil | freeze tous les agents non-critiques |

## 15.2 Reset manuel

Aucun breaker ne se reset tout seul (sauf délai explicite). Le fondateur reset via
slash command `/reset-breaker <name>` après avoir corrigé la cause racine.

✅ **Done quand** : un breaker artificiel `test_breaker` peut être trip via script et
empêche effectivement l'exécution d'un slash command qui le check.

---

# Partie 16 — Admin Control Panel

🎯 **Objectif** : interface privée que SEUL le fondateur consulte pour **piloter**
l'ensemble du système Argos Ops depuis n'importe où (desktop ou mobile). Pas un simple
monitoring : un vrai centre de commande qui permet de :

- Voir l'état de chaque agent en temps réel (running / stopped / throttled / breaker)
- **Démarrer / arrêter chaque agent à la volée** (un clic)
- **Régler la "gourmandise"** de chaque agent (intensity 1-10, daily_limit, token budget)
- Lire et résoudre les escalades Tier 2 en 1-clic
- Visualiser les KPIs business (MRR, leads, conversions, CAC)
- Monitorer la consommation tokens Claude Pro Max (D-017) + alertes si > 90 % du quota mensuel
- Trip / reset les circuit breakers manuellement
- Éditer la Knowledge Base inline (sans toucher au filesystem)
- Lire les logs de chaque agent run sans SSH

🧱 **Prérequis** : Parties 3 (table `agent_config`), 14 (juge), 15 (breakers).

📦 **Livrables** :
- Backend FastAPI `argos_ops/ops_dashboard/app.py`
- Frontend React + Vite + Tailwind dans `argos_ops/ops_dashboard/frontend/`
- Domaine privé `ops.omnividens.fr` routé via Caddy
- Auth multi-niveaux (Basic Auth + IP allowlist + 2FA TOTP optionnel)
- Wrapper Python `argos_ops/agent_runtime.py` que TOUS les slash commands consultent
  avant exécution (lit `agent_config`, applique enabled/intensity/limits)

🛠️ **Skills à utiliser (obligatoire, dans cet ordre)** :

1. **`ui-ux-pro-max`** — exploration des styles, palettes, font pairings, références
   visuelles AVANT toute écriture de code frontend. Le panel doit être dense, opérateur,
   inspiré des consoles cybersec (Splunk, Grafana, Wazuh, Linear), PAS du SaaS marketing
   pastel. Output attendu : choix figé de palette + typo + densité + layout pattern.
2. **`frontend-design`** — conception et code des composants une fois le style choisi
   par ui-ux-pro-max. Génère du React + Tailwind production-grade qui implémente
   exactement les choix figés.

## 16.1 Mécanisme de contrôle (le cœur du système)

L'admin panel ne fait pas QUE afficher. Il PILOTE l'exécution réelle des agents via
la table `agent_config` (définie en Partie 3) :

```
┌──────────────────────────────────────────────────────────────────┐
│ Admin Panel UI (React)                                           │
│   Toggle "ContentBot ON/OFF" → POST /api/agents/ContentBot       │
└──────────────────────────────────────────────────────────────────┘
                              ↓ écrit agent_config.enabled=false
┌──────────────────────────────────────────────────────────────────┐
│ Postgres : table agent_config                                    │
└──────────────────────────────────────────────────────────────────┘
                              ↑ lu à chaque run
┌──────────────────────────────────────────────────────────────────┐
│ cron lance /run-content-bot toutes les 4h                        │
│   ↓                                                              │
│   agent_runtime.run_if_enabled('ContentBot', do_work)            │
│     ↓ check enabled/intensity/limits                             │
│     ↓ skip avec log si désactivé                                 │
│     ↓ exécute avec scaling si actif                              │
└──────────────────────────────────────────────────────────────────┘
```

**Wrapper `argos_ops/agent_runtime.py`** que CHAQUE slash command appelle d'abord :

```python
async def run_if_enabled(agent_name: str, action: Callable[[AgentConfig], Any]) -> None:
    cfg = await load_config(agent_name)
    if not cfg.enabled:
        log.info(f"{agent_name} disabled by admin"); return
    if cfg.paused_until and cfg.paused_until > now():
        log.info(f"{agent_name} paused until {cfg.paused_until}"); return
    if await daily_limit_reached(agent_name, cfg):
        log.info(f"{agent_name} daily_limit reached"); return
    if await token_budget_exceeded(agent_name, cfg):
        log.warning(f"{agent_name} token budget exceeded"); return
    if await any_breaker_tripped_for(agent_name):
        log.error(f"{agent_name} blocked by breaker"); return
    await action(cfg)  # cfg.intensity_level scale les volumes en interne
```

L'`intensity_level` (1-10) sert à scaler le travail réel de l'agent. Exemples :
- ContentBot : intensité 5 = 3 posts/jour, intensité 10 = 6 posts/jour, intensité 1 = 1
- OutboundBot : intensité 5 = 30 emails/jour, intensité 10 = 50, intensité 1 = 5

## 16.2 Pages et fonctionnalités

### 16.2.1 Overview (homepage)
- 5 KPIs en grand : MRR, leads J-1, conversions J-1, CAC blended, escalades en attente
- Sparklines 7j sous chaque KPI
- État global du système : 12 lampes (1 par agent) — vert/jaune/rouge selon dernière run
- Banner d'alerte rouge si breaker actif ou escalade P0 non lue
- Refresh auto via SSE toutes les 10 s

### 16.2.2 Agents Control (LA page la plus importante)

Liste des 12 agents en cartes ou tableau dense, pour chaque agent :

| Élément UI | Action |
|------------|--------|
| **Toggle ON/OFF** géant | Active / désactive l'agent (persisté en DB, prend effet immédiat) |
| **Slider intensité 1-10** | Règle la "gourmandise" en live |
| **Champ Schedule cron** | Édite le cron, validé en live (`croniter` côté backend) |
| **Daily limit** | Volume max d'actions par jour (NULL = pas de limite) |
| **Token budget** | Quota LLM/jour (NULL = pas de limite) |
| Bouton **Run now** | Lance l'agent une fois manuellement (subprocess `claude --print`) |
| Bouton **Pause 1h** | `paused_until = now() + 1h` |
| Bouton **Pause 24h** | `paused_until = now() + 24h` |
| Bouton **Logs** | Ouvre un drawer avec les 50 derniers `agent_runs` |
| Mini graphe | Runs réussis / échoués sur 30 jours |
| Coût estimé | J-1 + cumul du mois en cours |

L'admin peut donc en 5 secondes : kill un agent qui dérive, baisser l'intensité d'un
agent qui consomme trop, ajouter une pause préventive avant un weekend, lancer
manuellement un test.

### 16.2.3 Breakers
- Liste des 10 breakers définis en P15
- Pour chaque : état (vert/rouge), raison du trip si rouge, historique des 10 derniers trips
- Bouton **Trip manuellement** (utile pour kill préventif type "je pars en vacances")
- Bouton **Reset** (avec confirmation, écrit qui a reset dans `breakers.notes`)

### 16.2.4 Escalations Queue
- Liste des escalades Tier 2 triées par priorité puis ancienneté
- Pour chaque : agent source, contexte (mail draft, ticket, post à valider), action proposée
- Boutons : **Approuver et envoyer** / **Rejeter** / **Réécrire** (drawer édition) / **Snooze 4h**
- Compteur "x escalades en retard SLA 24h" en rouge dans le header
- Cible : vider la file en 5 min/jour, 2× par jour

### 16.2.5 KPIs & Trends
- Graphes 30j / 90j / 1an : MRR, leads, conversions, churn, CAC, NRR
- Top 10 sources de leads
- Top 10 keywords organiques (depuis SEOBot / Google Search Console)
- Funnel visiteur → lead → démo → client
- Coût par agent du mois en cours vs précédent

### 16.2.6 Logs Viewer
- Table `agent_runs` paginée avec filtres : agent, statut, date range, recherche texte
- Détail d'un run en clic : JSON brut + sortie texte + erreurs + tokens consommés
- Export CSV pour analyses ad-hoc ou debugging

### 16.2.7 Knowledge Base Editor
- Liste les 6 fichiers markdown de la KB
- Édition inline (Monaco editor) avec preview
- Bouton **Rebuild embeddings** qui relance `seed_kb.py` sur le fichier modifié
- Diff vs version git (utile pour rollback rapide)

### 16.2.8 Settings
- Édition config globale Argos Ops (seuils, quotas par défaut)
- Test des intégrations en 1 clic (LinkedIn / Mastodon / Stripe / Gmail / Discord)
  → ping API, montre le résultat
- Régénération des tokens OAuth qui ont expiré (relance le flow OAuth)
- Liste des skills locaux installés
- Activation 2FA TOTP

## 16.3 Stack technique

| Couche | Choix | Justification |
|--------|-------|---------------|
| Backend | FastAPI dans `argos_ops/ops_dashboard/app.py` | Partage venv et DB du projet, async natif |
| Frontend | React + Vite + Tailwind | Cohérent avec frontend SecHunter, écosystème connu |
| Real-time | SSE (Server-Sent Events) | Plus simple que WebSocket, suffit pour push état |
| Charts | Recharts ou Apex | Léger, suffisant pour les graphes ops |
| Code editor (KB) | Monaco (VS Code engine) | Standard, syntax highlight markdown |
| Routing | Caddy → bloc `ops.omnividens.fr` → 127.0.0.1:9000 | Caddy déjà en prod, TLS auto |

## 16.4 Auth multi-niveaux

| Niveau | Mécanisme | Quand activer |
|--------|-----------|---------------|
| 1 | **Basic Auth** via Caddy (login/password unique) | Dès phase 16.A |
| 2 | **IP allowlist** (ton IP fixe ou Tailscale) | Dès phase 16.A |
| 3 | **TOTP 2FA** via lib `pyotp` + app Authy/Aegis | Phase 16.D, optionnel |
| 4 | **Session tokens** (table `admin_sessions`, expire 8h) | Dès phase 16.B |

Pas de multi-utilisateur. Pas d'OAuth Google. Solo founder = auth simple et solide.

## 16.5 Design philosophy

**À explorer obligatoirement via `ui-ux-pro-max` AVANT de coder** :

Inspirations cibles :
- **Wazuh** / **Splunk** / **Grafana** — dense, sobre, dark-mode-first, beaucoup d'info
- **Linear** — transitions ultra-rapides, raccourcis clavier (J/K nav, ⌘K palette)
- **Railway** / **Vercel dashboard** — bonne combinaison "data + actions"

À éviter :
- Look "SaaS marketing" pastel (Stripe, Notion) — pas adapté à un cockpit opérateur
- White space excessif — chaque pixel doit porter de l'info utile
- Animations décoratives — uniquement des transitions fonctionnelles

Choix à figer dans la session `ui-ux-pro-max` (consigné dans `docs/UI_DECISIONS.md`) :
- Palette (proba : zinc/slate base + 1 accent → vert healthy / orange warning / rouge alarm)
- Typographie (mono pour data, sans-serif dense pour UI — Inter ou Geist)
- Densité (info-dense, ratio 30 % padding / 70 % contenu)
- Pattern de layout (sidebar fixe + topbar status + main + drawer pour détails)
- Mobile : version simplifiée focalisée sur Overview + Agents Control (pour pilotage tel)

## 16.6 Implémentation par phases

Pour ne pas tout construire d'un coup, on découpe en 4 phases qui s'étalent du
Sprint 1 au Sprint 4. Phase 16.A devient utile dès qu'on a quelques agents Sprint 1.

| Phase | Sprint | Pages | Fonctionnalités |
|-------|--------|-------|-----------------|
| **16.A — MVP** | Sprint 1 (post P7) | Overview + Agents Control read-only + Logs | Voir mais pas piloter encore |
| **16.B — Control** | Sprint 2 (post P11) | + Toggle ON/OFF + Sliders + Run now + Breakers control | Pilotage actif des agents |
| **16.C — Escalations** | Sprint 3 (post P14) | + Escalations queue + Settings | Vidage Tier 2 en 5 min/jour |
| **16.D — Advanced** | Sprint 4 | + KB editor + KPIs avancés + 2FA TOTP | Polish final, plus jamais de SSH |

**Important** : la table `agent_config` (P3) doit être créée dès le bootstrap car les
agents Sprint 1 doivent déjà appeler `agent_runtime.run_if_enabled()`. Sinon il faut
réécrire tous les agents quand on ajoute le panel — anti-pattern.

✅ **Done quand** :
- **Phase 16.A** : tu vois l'état des 4 premiers agents en temps réel sur ton tel
- **Phase 16.B** : tu peux stopper un agent qui dérive en 1 clic depuis le canapé,
  baisser son intensité, le relancer manuellement après correction
- **Phase 16.C** : tu vides ta file Tier 2 en 5 min/jour, 2× par jour
- **Phase 16.D** : 100 % des changements opérationnels passent par le panel,
  zéro `ssh` manuel sauf incident infra grave

---

# Partie 17 — Conformité RGPD / AI Act / Bloctel

🎯 **Objectif** : `docs/COMPLIANCE.md` à jour, les agents respectent les contraintes.

🧱 **Prérequis** : aucune (peut être fait en parallèle).

📦 **Livrables** :
- `docs/COMPLIANCE.md` exhaustif
- Page `https://omnividens.fr/legal/ai-disclosure` publique
- Mécanisme opt-out fonctionnel (table `unsubscribes` + endpoint `/unsubscribe`)
- Registre des traitements RGPD

## 17.1 Cold email (BtoB)

- Intérêt légitime documenté dans le registre
- Opt-out 1-clic obligatoire dans le footer
- Suppression sous 7 jours après opt-out
- Pas d'envoi à des particuliers (filtre TLD + heuristiques email perso)

## 17.2 IA voix (téléphonie, phase 2)

- AI Act UE : annoncer "vous êtes en relation avec une intelligence artificielle" en
  début d'appel
- Bloctel : checker la liste FR avant tout appel BtoC
- BtoB : Bloctel ne s'applique pas mais le respect des heures et de l'opt-out reste
  bonne pratique

## 17.3 Données prospects / clients

- Registre des traitements RGPD (modèle CNIL gratuit)
- Page `/legal/privacy` du site à jour avec : finalités, durée conservation, droits
  (accès / rectification / suppression / portabilité)
- DPO externe à prévoir si > 250 prospects ou > 50 clients (~80 €/mois)

## 17.4 Avis clients

> Note : la section « Chatbot site » de la version v1 du plan est supprimée
> ([D-019](DECISIONS.md#d-019--abandon-d%C3%A9finitif-du-chatbot-widget-site-p8-cancelled)).

- JAMAIS générer de faux avis (interdit, sanction CNIL + DGCCRF)
- Solliciter des avis vrais via email post-onboarding J+30
- Modérer mais ne pas supprimer les avis négatifs sans motif sérieux

✅ **Done quand** : `docs/COMPLIANCE.md` rédigé, opt-out testé, page `/legal/privacy`
publiée, registre RGPD initialisé.

---

# Partie 18 — Inventaire des skills à créer

🎯 **Objectif** : suivre l'inventaire des skills locaux du projet `argos-ops` au fil des
parties.

🛠️ **Skills à utiliser** :
- `skill-creator` à chaque création (toujours)

## 18.1 Liste exhaustive

| Skill | Crée en partie | Réutilisé par |
|-------|----------------|---------------|
| `digest-builder` | 4 | AnalyticsBot |
| `gmail-ops` | 5 | EmailBot, OutboundBot |
| `email-classifier` | 5 | EmailBot |
| `kb-rag` | 6 | EmailBot, SupportBot, ContentBot, OutboundBot |
| `stripe-ops` | 7 | FinanceBot |
| ~~`chat-orchestrator`~~ | ~~8~~ | ~~ChatBot~~ — **annulé par D-019** |
| `content-writer` | 9 | ContentBot |
| `content-scheduler` | 9 | ContentBot |
| `serp-analyzer` | 10 | SEOBot |
| `ads-optimizer` | 12 | AdBot |
| `ads-creative-writer` | 12 | AdBot |
| `lead-enricher` | 13 | OutboundBot |
| `outbound-personalizer` | 13 | OutboundBot |
| `claude-judge` | 14 | TOUS les agents sortants |

## 18.2 Règle générale

À chaque fois qu'une logique LLM apparaît dans 2 commands différents, **extraire en skill**
via `skill-creator`. Le skill devient l'unité de réutilisation entre agents.

## 18.3 Skills hors `argos-ops` mobilisés

Pour la conception du projet lui-même (fondateur en train de coder avec Claude Code) :

- `skill-creator` — créer chaque skill `argos-ops`
- `frontend-design` — Ops Dashboard (Partie 16). _(La Partie 8 chatbot widget est
  annulée — D-019.)_
- `ui-ux-pro-max` — exploration de styles si plusieurs options à comparer (Partie 16)
- `claude-api` — si un jour l'abonnement Claude Code ne suffit plus et on bascule sur
  l'API directe pour certains agents (phase 3)

---

# Partie 19 — Maintenance et observabilité

🎯 **Objectif** : que le système tourne tout seul pendant 30+ jours sans dérive.

🧱 **Prérequis** : tout ce qui précède.

📦 **Livrables** :
- Hook `PostToolUse` qui log chaque action d'agent dans `agent_runs`
- Hook `PreToolUse` qui consulte les breakers
- Script `scripts/health_check.py` qui vérifie : DB up, Redis up, cron running, dernier run
  de chaque agent < 25 h
- Alertes Discord si un agent n'a pas tourné depuis > X heures

## 19.1 Observabilité

Trois niveaux de logs :

1. **`agent_runs` table** — résumé par exécution (start, end, status, output)
2. **Loguru file logs** — détail par run, rotation 7 jours, dans `~/argos-ops/logs/`
3. **Discord** — événements humains (escalades, breakers trips, digest matin)

## 19.2 Coût mensuel attendu (en croisière)

| Poste | Estimation |
|-------|------------|
| Abonnement Claude Pro/Max | inchangé (runtime LLM + embeddings deleg via local — D-017) |
| Serveur (déjà en prod) | inchangé (couche données seulement) |
| Domaine secondaire outbound | ~10 €/an = 1 €/mois |
| API LLM tierces | **0 € (aucune utilisée — D-017)** |
| Embeddings | **0 € (multilingual-e5-base local CPU — D-017)** |
| Tout le reste | 0 € |
| **Total nouveau** | **~1 €/mois** |

## 19.3 KPIs santé système

- Taux de slash commands réussis > 98 %
- Latence p95 EmailBot < 30 s
- 0 breaker actif > 4 h
- 0 escalade Tier 2 sans réponse > 48 h

✅ **Done quand** : 7 jours consécutifs avec santé système verte, 0 incident humain.

---

# Partie 20 — Argos Memory (mémoire vivante partagée multi-agents)

🎯 **Objectif** : doter la flotte Argos Ops d'une **mémoire grandissante,
partagée et interrogeable** par tous les agents, persistée 100 % localement
sur le poste du fondateur, avec comme seule limite la capacité disque de
la machine. Chaque agent gagne en performance individuelle (contexte
historique de ses propres runs) ET la flotte gagne en cohérence collective
(les agents se nourrissent mutuellement de ce qu'ils ont appris).

🧱 **Prérequis** :
- **P3** (CRM + KB + pgvector + fastembed) — réutilise la même stack
- **P6** (`kb-rag` skill) — le pattern recherche sémantique est étendu ici
- **P14** (`claude-judge`) — les verdicts du juge sont une source mémoire
  prioritaire (détection de dérive de ton)
- **P15** (breakers) — un breaker `memory_storage_full` est ajouté
- **P19** (`health_check.py`) — monitoring de la taille mémoire et de la
  fraîcheur des écritures

📦 **Livrables** :
- Migration `argos_ops/crm/migrations/0007_memory.sql` (tables
  `memory_items` + `memory_chunks` + index)
- Module Python `argos_ops/memory/` (`__init__.py`, `archive.py`,
  `search.py`, `redact.py`, `gc.py`)
- Hook automatique dans `argos_ops/agents/base.py:run_agent()` qui
  archive chaque `RunResult` (rétroactif sur les 8 agents existants)
- Arborescence `data/memory/raw/<YYYY-MM-DD>/<agent>/<run_id>.json` +
  `data/memory/insights/<YYYY-WW>/<theme>.md`
- Skill `.claude/skills/argos-memory/` (équivalent `kb-rag` mais sur la
  mémoire vivante des agents)
- Skill `.claude/skills/memory-curator/` (extraction d'insights hebdo)
- Skill `.claude/skills/memory-auditor/` (audit cohérence + nettoyage)
- Slash commands `/curate-memory`, `/audit-memory`, `/memory-gc`
- Tests (~40 prévus, couvre archive, redact, search, gc)
- Breaker `memory_storage_full` (seuil P15, déclenche à 80 % de la
  partition réservée)
- Doc `docs/ARGOS_MEMORY.md` — référence opérateur

## 20.1 Concept et gap actuel

**Le problème** que cette partie résout :

| Agent | Ce qu'il produit | Qui peut en bénéficier aujourd'hui |
|-------|------------------|-------------------------------------|
| EmailBot (P5) | classifications, drafts, threads | personne (sauf opérateur via `/check-emails`) |
| SupportBot (P6) | réponses RAG, escalades | personne (chaque ticket repart de zéro) |
| FinanceBot (P7) | relances, événements MRR | personne (l'historique Stripe reste dans Stripe) |
| ContentBot (P9-DRAFT) | drafts par canal | personne (pas de mémoire des topics déjà couverts) |
| AdBot (P12 shadow) | drafts d'annonces, recos CSV | personne (l'historique perdu d'une semaine sur l'autre) |
| claude-judge (P14) | verdicts factuels/tone/legal | personne (pas de détection de dérive sur N jours) |
| OutboundBot (P13, à venir) | personalizations, séquences | **CRITIQUE** : sans mémoire = doublons de contact = risque RGPD |

**La distinction qu'il faut tenir** : Argos Memory n'est PAS *un seul*
mécanisme. C'est deux problèmes différents, résolus par deux outils
différents au sein du même système :

1. **Filing (archivage propre)** — chaque output doit être persisté de
   façon **déterministe**, sans LLM, dans une arborescence prévisible.
   Pas de jugement créatif, pas de paraphrase, pas de classification IA
   à ce niveau. Juste de la persistance fiable.
2. **Apprentissage (insights)** — les patterns intéressants ne se
   trouvent pas dans 1 output isolé, mais dans l'agrégation de N outputs
   sur N jours. C'est là qu'un LLM (Claude Code) intervient, en mode
   batch hebdomadaire, pour produire des notes synthétiques.

> ❌ **Ne PAS faire** : N agents-rangeurs IA qui se courent après pour
> classer chaque output au fur et à mesure. C'est over-engineered,
> non-déterministe (un LLM qui renomme un fichier peut le perdre), et
> coûte des tokens à chaque run. Le filing brut DOIT être en Python pur.

## 20.2 Architecture en 5 couches

```
┌────────────────────────────────────────────────────────────────┐
│  COUCHE 5 — Auditor skill (LLM, manuel ou hebdo)               │
│  Audit cohérence + GC user-controlled                           │
│  → /memory-gc EmailBot 90d                                      │
└────────────────────────────────────────────────────────────────┘
                              ▲
┌────────────────────────────────────────────────────────────────┐
│  COUCHE 4 — Curator skill (LLM batch hebdo)                     │
│  Extraction d'insights agrégés (PII-free by design)             │
│  → data/memory/insights/<YYYY-WW>/<theme>.md                    │
└────────────────────────────────────────────────────────────────┘
                              ▲
┌────────────────────────────────────────────────────────────────┐
│  COUCHE 3 — Index sémantique (pgvector, fastembed, REDACTED)    │
│  table memory_chunks — recherche par similarité multi-agents     │
│  → "trouve drafts proches de ce topic"                          │
└────────────────────────────────────────────────────────────────┘
                              ▲
┌────────────────────────────────────────────────────────────────┐
│  COUCHE 2 — Index structuré SQL (Postgres, REDACTED)            │
│  table memory_items — métadonnées + tags + lead_id + path        │
│  → "tous les runs d'EmailBot sur lead_id=42 cette semaine"      │
└────────────────────────────────────────────────────────────────┘
                              ▲
┌────────────────────────────────────────────────────────────────┐
│  COUCHE 1 — Raw archive (déterministe, FULL fidelity)           │
│  data/memory/raw/<YYYY-MM-DD>/<agent>/<run_id>.json              │
│  → hook automatique dans run_agent()                             │
└────────────────────────────────────────────────────────────────┘
                              ▲
                       BaseAgent.run() → RunResult
```

**Règle d'or** : un agent qui veut interroger la mémoire passe par les
**couches 2 ou 3** (redacted, indexées). Seul l'opérateur humain accède
à la **couche 1** (raw plein), via le Admin Panel ou la CLI Python.

## 20.3 Schéma DB (P20.A) — migration `0007_memory.sql`

```sql
-- =============================================================================
-- Argos Memory — index structuré (couche 2)
-- =============================================================================
CREATE TABLE IF NOT EXISTS memory_items (
  id BIGSERIAL PRIMARY KEY,
  agent_run_id BIGINT REFERENCES agent_runs(id) ON DELETE CASCADE,
  agent_name TEXT NOT NULL,            -- 'EmailBot', 'ContentBot', etc.
  item_type TEXT NOT NULL,             -- 'email_draft' | 'classification' |
                                       --   'judge_verdict' | 'content_draft' |
                                       --   'ad_variant' | 'support_answer' |
                                       --   'outbound_personalization' | etc.
  raw_path TEXT NOT NULL,              -- 'data/memory/raw/2026-05-15/EmailBot/42.json'
  redacted_summary TEXT,               -- résumé PII-free indexable, ~500 chars max
  tags TEXT[] DEFAULT '{}',            -- ['lead-chaud', 'rgpd', 'fr-FR', ...]
  lead_id BIGINT REFERENCES leads(id) ON DELETE SET NULL,
  company_id BIGINT REFERENCES companies(id) ON DELETE SET NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  -- Pour le GC user-controlled (P20.D) :
  retention_class TEXT NOT NULL DEFAULT 'standard'
    CHECK (retention_class IN ('ephemeral', 'standard', 'permanent'))
);
CREATE INDEX IF NOT EXISTS idx_memory_items_agent ON memory_items(agent_name);
CREATE INDEX IF NOT EXISTS idx_memory_items_type ON memory_items(item_type);
CREATE INDEX IF NOT EXISTS idx_memory_items_lead ON memory_items(lead_id) WHERE lead_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_memory_items_created_at ON memory_items(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_memory_items_tags ON memory_items USING GIN(tags);

-- =============================================================================
-- Argos Memory — index sémantique (couche 3)
-- =============================================================================
CREATE TABLE IF NOT EXISTS memory_chunks (
  id BIGSERIAL PRIMARY KEY,
  memory_item_id BIGINT NOT NULL REFERENCES memory_items(id) ON DELETE CASCADE,
  chunk_index INT NOT NULL,
  content TEXT NOT NULL,               -- REDACTED — pas de PII
  content_hash TEXT NOT NULL,          -- sha256 pour idempotence
  embedding vector(768),               -- même modèle que kb_chunks (D-017)
  UNIQUE (memory_item_id, chunk_index)
);
CREATE INDEX IF NOT EXISTS idx_memory_chunks_embedding
  ON memory_chunks USING ivfflat (embedding vector_cosine_ops)
  WITH (lists = 100);
```

**Pourquoi tables séparées de `kb_chunks`** : la KB est statique
(documents produit rédigés à la main, ~50 chunks stables), la mémoire
est dynamique (potentiellement 100k+ chunks après 1 an). Index ivfflat
optimisés différemment, et on évite que la mémoire pollue la recherche
KB pure (`/run-support-tier1` doit chercher dans la KB produit, pas dans
les drafts d'emails passés).

**Pourquoi `retention_class`** : c'est le hook pour le GC user-controlled
(Q3 répondue 2026-05-15). Par défaut tout est `standard`, mais l'agent
peut tagger ses outputs `ephemeral` (drafts intermédiaires) ou
`permanent` (verdicts judge, qu'on ne veut jamais perdre).

## 20.4 Module Python — `argos_ops/memory/`

API publique (depuis n'importe quel agent) :

```python
from argos_ops.memory import archive, search, redact

# COUCHE 1+2 — écriture (appelée automatiquement par run_agent, mais
# disponible aussi pour des écritures sub-run granulaires).
await archive.write(
    agent_run_id=run.id,
    agent_name="EmailBot",
    item_type="email_draft",
    full_payload={"subject": "...", "body": "...", "to": "..."},
    tags=["lead-chaud", "fr-FR"],
    lead_id=42,
    retention_class="standard",
)
# → écrit data/memory/raw/2026-05-15/EmailBot/<uuid>.json (full)
# → applique redact.redact_for_index() pour le résumé
# → INSERT INTO memory_items
# → embed le redacted_summary + INSERT INTO memory_chunks

# COUCHE 2 — recherche SQL filtrée
items = await search.search_sql(
    agent_name="EmailBot",
    item_type="email_draft",
    lead_id=42,
    since=timedelta(days=7),
)

# COUCHE 3 — recherche sémantique cross-agent
similar = await search.search_semantic(
    query="comment relancer un lead silent depuis 14 jours",
    agent_name=None,         # tous agents
    item_type=None,          # tous types
    top_k=5,
)
# → renvoie List[MemoryHit] avec score cosine + redacted_summary
# → l'agent appelant peut ensuite charger le raw via search.load_raw(item_id)
#   si autorisation (cf. § 20.6)
```

`redact.py` fournit `redact_for_index(text: str, mode: Literal["aggressive","standard"]) -> str` qui retire :
- Emails (regex `\b[\w.+-]+@[\w.-]+\.\w+\b` → `<email>`)
- Téléphones FR/intl (`<phone>`)
- IBAN/RIB français (`<iban>`)
- N° de CB (Luhn validate → `<cc>`)
- IPv4/IPv6 publiques (`<ip>`)
- Noms propres détectés via heuristique (Marc Dupont → `<person>`) —
  optionnel, activable par flag, faux positifs à surveiller

**Ne PAS rédacter** : noms de **société** (personne morale, hors RGPD),
domaines publics, numéros de tickets internes, lead_id internes.

## 20.5 Hook automatique dans `BaseAgent` (rétroactif)

Modification de `argos_ops/agents/base.py:run_agent()` après le
`complete_agent_run` final :

```python
# ... après complete_agent_run() existant
if result.status == "success" and result.extras.get("memory") is not None:
    await archive.write(
        agent_run_id=run_id,
        agent_name=agent.name,
        item_type=result.extras["memory"]["item_type"],
        full_payload=result.extras["memory"]["payload"],
        tags=result.extras["memory"].get("tags", []),
        lead_id=result.extras["memory"].get("lead_id"),
        company_id=result.extras["memory"].get("company_id"),
        retention_class=result.extras["memory"].get("retention", "standard"),
    )
```

**Pour rendre P20 rétroactif sur les 8 agents existants** : chaque agent
(EmailBot, SupportBot, FinanceBot, DigestBuilder, etc.) ajoute dans son
`RunResult.extras["memory"] = {...}` à la fin de son `run()`. C'est
une modification **localisée** (1 dict supplémentaire par agent), non
breaking si l'agent oublie (le hook est `if ... is not None`).

## 20.6 Anonymisation et privacy (Q4 répondue 2026-05-15)

Stratégie **par couche** :

| Couche | Contenu | PII ? | Accès |
|--------|---------|-------|-------|
| 1 — Raw archive | Plein, fidélité totale | ✅ contient PII | Opérateur humain uniquement (CLI Python, Admin Panel P16.D) |
| 2 — SQL index (`memory_items.redacted_summary`) | Résumé sans PII | ❌ redacted via `redact.py` | Agents autorisés (cf. ACL) |
| 3 — Semantic index (`memory_chunks.content`) | Chunks redacted | ❌ redacted | Tous les agents |
| 4 — Insights curator | Patterns agrégés | ❌ par design (parle de N événements, pas de Marc Dupont) | Tous les agents, opérateur |

**ACL minimale (v1)** : tous les agents Argos Ops ont accès lecture aux
couches 2/3/4 (c'est l'intérêt). La couche 1 (raw) est accessible
uniquement via :
- CLI Python `argos_ops.memory.search.load_raw(item_id)`
- Admin Panel P16.D (vue détail "Mémoire" avec auth 2FA)

**Conformité RGPD** :
- `memory_items` lié à `leads`/`companies` via FK → si un lead exerce son
  droit à l'effacement (RGPD art. 17), `ON DELETE CASCADE` purge
  automatiquement ses items mémoire
- Documenter dans `data/legal/privacy.md` : ajout d'un traitement
  "Mémoire agents — base d'apprentissage opérationnel"
- Documenter dans `data/legal/ai-disclosure.md` : conformément à
  l'AI Act, mentionner que les outputs des agents sont conservés pour
  audit et apprentissage interne

## 20.7 Curator skill `memory-curator` (P20.C)

Skill markdown invoqué par `/curate-memory` (hebdo via Task Scheduler
ou à la demande). Lit les `memory_items` des 7 derniers jours, groupe
par `item_type` × `tags`, et écrit des notes synthétiques :

```
data/memory/insights/2026-W20/
├── content_topics_covered.md      # "ContentBot a publié 4× sur supply chain S20"
├── outbound_objections.md         # "3 leads ont objecté sur le pricing"
├── judge_drift_signals.md         # "claude-judge note tone -10pts vs S19"
├── support_unresolved.md          # "2 questions Tier 1 escaladées en Tier 2"
└── ad_creative_winners.md         # "headline 'audit en 48h' CTR x2 vs autres"
```

Garde-fous :
- Lit uniquement couche 2 (SQL index, redacted)
- N'a pas accès au raw — impossible de fuiter une PII dans un insight
- Output systématiquement passé à `claude-judge` (P14) avant écriture —
  un insight tagué `tone: <70` est mis en queue plutôt qu'écrit

## 20.8 Auditor skill + GC user-controlled (P20.D, réponse Q3)

`memory-auditor` skill + 3 slash commands :

```bash
/audit-memory                       # sans arg : liste orphans, untagged, taille
/memory-gc EmailBot 90d             # purge raw + items > 90j pour EmailBot
/memory-gc --retention ephemeral    # purge tous les items 'ephemeral' > 7j
```

Le GC est **toujours user-initiated** (réponse Q3 du fondateur 2026-05-15) :
- Pas de cron automatique de purge
- L'auditor *suggère* (`💡 EmailBot : 12k items > 90j, ~340 MB. Lance
  /memory-gc EmailBot 90d pour purger.`) mais n'exécute jamais
- L'opérateur valide chaque purge

`/memory-gc <agent> <duration>` :
1. Liste les items concernés (dry-run par défaut)
2. Demande confirmation explicite `[y/N]`
3. Supprime les rows `memory_items` (cascade vers `memory_chunks`)
4. Supprime les fichiers `data/memory/raw/<date>/<agent>/*.json` correspondants
5. Log dans `agent_runs` (agent `MemoryGC`) avec count avant/après

## 20.9 Phasage P20.A → P20.D

| Sous-partie | Périmètre | Effort | Dépendances |
|-------------|-----------|--------|-------------|
| **P20.A** | Migration DB + module `argos_ops/memory/archive.py` + `redact.py` + hook BaseAgent + tests | ~1 session | P3 |
| **P20.B** | `argos_ops/memory/search.py` (sémantique) + skill `argos-memory` | ~0.5 session | P20.A + P6 (kb-rag) |
| **P20.C** | Skill `memory-curator` + `/curate-memory` + Task Scheduler hebdo | ~0.5 session | P20.B + P14 (judge) |
| **P20.D** | Skill `memory-auditor` + `/audit-memory` + `/memory-gc` + breaker `memory_storage_full` | ~0.5 session | P20.A + P15 |

**Ordre d'exécution recommandé** : P20.A en premier (foundation, débloque
les écritures automatiques sur les 8 agents existants), puis P20.B
(recherche sémantique, débloque la valeur cross-agent), puis P20.C/D en
parallèle (curator et auditor sont indépendants).

## 20.10 Bénéfices concrets par agent (boucle d'amélioration)

| Agent | Ce que la mémoire débloque |
|-------|----------------------------|
| EmailBot | "ce lead a déjà été contacté il y a 3 mois, voici le thread" → 0 doublon |
| SupportBot | "questions similaires escaladées dans le passé" → améliore le RAG |
| FinanceBot | "relance J+15 sur ce client = pattern habituel" → ton calibré |
| ContentBot (P9 full) | "topic supply chain couvert 2× ce mois sur LinkedIn" → varie l'angle |
| AdBot (P12.B live) | "variante headline 'audit 48h' = winner S19" → réutilise patterns gagnants |
| OutboundBot (P13) | "ce domaine a reçu une séquence il y a 6 mois, status: no-reply" → priorise nouveaux contacts |
| claude-judge | "drift score tone -8pts vs moyenne 30j" → alerte fondateur |
| TrendSpotter (Annexe D) | corrèle tendances détectées vs sujets déjà couverts |

## 20.11 KPIs santé mémoire

- Taille totale `data/memory/raw/` (alerte > 80 % partition)
- Latence p95 `search.search_semantic()` < 500 ms (sur 100k items)
- Taux d'items orphelins (sans `memory_chunks` après 24 h) < 1 %
- Taux d'écriture rétroactive : 8/8 agents existants émettent
  `extras["memory"]` en sortie de `run()`

## 20.12 Anti-patterns à éviter

- ❌ Faire écrire les agents directement dans `data/memory/raw/` sans
  passer par `archive.write()` — bypass l'index, item devient orphelin
- ❌ Indexer en sémantique du contenu brut non-redacted — fuite PII
  garantie quand un autre agent l'utilisera comme contexte
- ❌ Laisser le curator écrire des insights sans passage par
  `claude-judge` — risque d'hallucination dans la mémoire long terme,
  pire que pas de mémoire
- ❌ Cron auto de purge — viole la décision Q3 (user-controlled),
  risque de perte irréversible (un GC raté écrase un verdict judge clé)
- ❌ Stocker dans `memory_items.redacted_summary` plus de 500 chars —
  l'embedding mpnet a une fenêtre, et l'index ivfflat se dégrade vite

✅ **Done quand** :
- P20.A : migration appliquée, hook BaseAgent en place, 8 agents
  existants ré-câblés pour émettre `extras["memory"]`, tests passent
  (~40 tests)
- P20.B : `search_semantic()` retourne des résultats pertinents sur un
  corpus de 100+ items réels
- P20.C : 1 cycle hebdo de curator produit des insights validés par
  `claude-judge` et utiles à l'opérateur
- P20.D : `/memory-gc` testé sur 1 agent (dry-run + apply), breaker
  `memory_storage_full` câblé, doc opérateur livrée

---

# Partie 21 — Paramétrage inter-agents (capabilities pull-based)

🎯 **Objectif** : permettre au fondateur de **configurer ce que chaque
agent a le droit de faire vis-à-vis des outputs des autres agents**,
sans recâbler le code à chaque combinaison désirée. Modèle **pull** :
aucun agent ne *déclenche* un autre agent ; c'est l'agent qui, à son
propre run normal, va chercher dans la mémoire ce que ses voisins ont
produit dans son champ de compétence, et l'utilise comme contexte.

Exemples cibles :
- **TargetSpotter** lit les `email_inbound` d'EmailBot et les leads
  qualifiés en `lead-chaud` → enrichit son backlog de prospection au
  prochain run
- **Agent compta** lit les outputs `stripe_event` et `dunning_sent` de
  FinanceBot → reconcilie sa propre vision comptable
- **BudgetWatcher** lit les `ad_variant_performance` d'AdBot **ET** les
  `lead_volume` de TargetSpotter → ajuste sa recommandation budget (et
  peut écrire un `budget_advice` que AdBot lit à son prochain run = boucle
  douce)

🧱 **Prérequis** :
- **P20 (Argos Memory) hard prerequisite** — c'est le bus de
  communication. Sans `memory_items` indexés, il n'y a rien à lire.
- **P16 (Admin Panel)** — la vue matrice de configuration est une
  nouvelle page (P16.E)
- **P15 (breakers)** — toute capability `react` ou `write_back`
  respecte les breakers de l'agent ciblé

📦 **Livrables** :
- Migration `argos_ops/crm/migrations/0008_capabilities.sql`
  (table `agent_capabilities`)
- Module Python `argos_ops/capabilities/` (`__init__.py`,
  `loader.py`, `enforcer.py`, `writeback.py`, `cycles.py`)
- Helper `consume_capabilities(agent_name)` appelé en début de chaque
  `BaseAgent.run()` qui retourne le contexte pré-mâché à utiliser
- Helper `write_back(target_agent, payload, capability_id)` pour les
  agents autorisés à influencer un autre agent
- Extension `argos_ops/ops_dashboard/` : page **Câblage** (Wiring) —
  matrice subject × object avec édition à chaud
- Script `scripts/export_capabilities.py` → dump YAML
  `data/capabilities.yaml` (committable, audit git)
- Script `scripts/seed_capabilities.py` → applique le YAML en DB
  (idempotent, pour bootstrap/rollback)
- Tests (~25 prévus : default policy, deny override, cycle detection,
  write-back integrity)
- Breaker `capability_loop_detected` (P15) — déclenché si la couche
  cycle detection repère un pattern A→B→A en moins de 24h
- Doc `docs/AGENT_CAPABILITIES.md` — référence opérateur

## 21.1 Modèle pull confirmé (vs push/trigger)

**Rejeté pour v1** : modèle push/trigger (« quand A produit X, déclenche
B immédiatement »). Risques cascade, ping-pong, blow-up du daily_limit.

**Adopté** : modèle **pull opportuniste**. Chaque agent garde sa
cadence cron normale. Au début de son `run()`, il consulte ses
*capabilities* configurées et tire de la mémoire P20 les outputs
récents qui matchent. Latence = cadence cron de l'agent qui regarde
(`*/15` pour EmailBot, `0 8` pour DigestBuilder, etc.) — c'est
suffisant pour un système BtoB.

```
T0 :   EmailBot run (cron */15) → produit email_inbound (memory_item)
T+8m : TargetSpotter run (cron */15, décalé) → consume_capabilities()
       → SELECT * FROM memory_items
         WHERE agent_name='EmailBot'
           AND item_type='email_inbound'
           AND created_at > now() - interval '20 min'
           AND <filter de la capability>
       → enrichit son contexte avec ces items, fait son boulot habituel
```

Pas de trigger, pas de cascade instantanée. La « boucle douce » via
`write_back` (B écrit pour A, A le lit au prochain run) est possible
mais lente (1 cycle = 1 cadence cron de chaque côté).

## 21.2 Anatomie d'une capability

```python
@dataclass
class Capability:
    id: int                          # PK
    subject_agent: str               # qui regarde — "TargetSpotter"
    object_agent: str                # qui est regardé — "EmailBot"
    permission: Literal["read", "react", "write_back"]
    # ↑ "react" reste réservé pour P21.X future (push model)
    #   v1 implémente "read" et "write_back" uniquement.
    item_type_filter: list[str]      # ["email_inbound", "lead_qualified"]
    tag_filter: list[str] | None     # ['lead-chaud'] — None = pas de filtre
    enabled: bool                    # toggle on/off sans supprimer
    created_at: datetime
    updated_at: datetime
    notes: str | None                # raison textuelle pour audit
```

**Sémantique selon `permission`** :

- **`read`** (par défaut **ALLOW**) — `subject_agent` peut lire les
  `memory_items` de `object_agent` qui matchent les filtres.
  L'opérateur peut ajouter une row `enabled=False` pour **bloquer**
  une lecture précise (deny override).
- **`react`** — réservé futur. v1 = ignoré, lèvera `NotImplementedError`.
  Documenté pour ne pas devoir migrer la table plus tard.
- **`write_back`** (par défaut **DENY**) — `subject_agent` peut écrire
  un `memory_item` avec `item_type` préfixé `advice.*` (ex
  `advice.budget_adjust`) que `object_agent` lira à son prochain run.
  Nécessite une row `enabled=True` explicite — risque comportemental.

## 21.3 Schéma DB — migration `0008_capabilities.sql`

```sql
CREATE TABLE IF NOT EXISTS agent_capabilities (
  id BIGSERIAL PRIMARY KEY,
  subject_agent TEXT NOT NULL,
  object_agent TEXT NOT NULL,
  permission TEXT NOT NULL CHECK (permission IN ('read', 'react', 'write_back')),
  item_type_filter TEXT[] NOT NULL DEFAULT '{}',
  tag_filter TEXT[],                  -- NULL = pas de filtre tag
  enabled BOOLEAN NOT NULL DEFAULT true,
  notes TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (subject_agent, object_agent, permission, item_type_filter)
);
CREATE INDEX IF NOT EXISTS idx_capabilities_subject ON agent_capabilities(subject_agent);
CREATE INDEX IF NOT EXISTS idx_capabilities_object ON agent_capabilities(object_agent);

-- Audit trail : on enrichit agent_runs pour tracer ce qui a été consommé
ALTER TABLE agent_runs
  ADD COLUMN IF NOT EXISTS capabilities_consumed JSONB DEFAULT '[]'::jsonb;
-- ex : [{"capability_id": 7, "items_consumed": 12}, ...]
```

## 21.4 Module Python — `argos_ops/capabilities/`

API publique côté **agent qui consomme** :

```python
from argos_ops.capabilities import consume_capabilities

async def run(self) -> RunResult:
    # tirage opportuniste au début du run
    context = await consume_capabilities(agent_name=self.name)
    # context = {
    #   "EmailBot": [<MemoryItem>, ...],          # items récents matchés
    #   "FinanceBot": [<MemoryItem>, ...],
    # }
    # ... logique métier qui peut s'appuyer sur context ...
```

`consume_capabilities()` :
1. Lit `agent_capabilities` WHERE `subject_agent = me AND enabled = true AND permission = 'read'`
2. **Default policy** = ALLOW : si aucune row matchée, considère ouvert
3. **Deny override** : si une row `enabled = false` existe pour un object donné, bloque
4. Pour chaque object autorisé, fait `memory.search_sql()` avec
   `item_type IN (item_type_filter) AND tags @> tag_filter AND
   created_at > (last consume by me - safety window)`
5. Log dans `agent_runs.capabilities_consumed` (JSONB)

API publique côté **agent qui écrit-back** :

```python
from argos_ops.capabilities import write_back

await write_back(
    from_agent="BudgetWatcher",
    to_agent="AdBot",
    advice_type="budget_adjust",
    payload={"daily_cap_eur": 30, "rationale": "MRR -8% S20"},
)
# Vérifie qu'une capability write_back BudgetWatcher → AdBot existe
# et est enabled. Sinon raise CapabilityDenied.
# Crée un memory_item item_type='advice.budget_adjust' que AdBot
# lira via sa propre capability read AdBot ← *.
```

`cycles.py` — détection au moment de la création/édition d'une
capability `write_back` :
- Parcourt le graphe orienté des `write_back`
- Si l'ajout crée un cycle (A→B→A), refuse côté API DB
- Si une cascade indirecte est détectée à runtime (B lit A, écrit
  back pour A qui lit B etc.), déclenche le breaker
  `capability_loop_detected` (P15) — log Discord et désactive
  temporairement la nouvelle capability

## 21.5 Frontend Admin Panel — vue **Câblage** (P16.E)

Nouvelle page `ops_dashboard/templates/wiring.html` (et route
backend correspondante). Layout :

```
┌─────────────────────────────────────────────────────────────────────┐
│ Câblage inter-agents                                                 │
│ Configure ce que chaque agent peut lire ou influencer.               │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│   Sujet ↓ \ Objet →   EmailBot  FinanceBot  AdBot   TargetSpotter   │
│   ──────────────────  ────────  ──────────  ─────   ─────────────   │
│   EmailBot              —         ◌            ◌         ◌          │
│   FinanceBot            ◌          —           ◌         ◌          │
│   AdBot                 ◌         ●            —         ●R         │
│   TargetSpotter         ●R+filt   ◌            ◌          —         │
│   BudgetWatcher         ◌         ●R           ●W        ●R         │
│                                                                      │
│   Légende : ◌ open (default allow read)  ●R read configuré          │
│             ●W write-back grant         ●D deny explicite           │
│             +filt = filtre item_type ou tag actif                   │
└─────────────────────────────────────────────────────────────────────┘
```

Click sur une cellule → drawer latéral pour configurer :
- Permission (`read` / `write_back`)
- `item_type_filter` (multi-select sur les types connus)
- `tag_filter`
- `enabled` toggle
- `notes` (textarea — pourquoi cette capability ? trace pour audit)

Une bande horizontale en bas de la page affiche les **3 derniers
write-back** appliqués (`from → to · advice_type · timestamp`) pour
que l'opérateur voie en glance qui influence qui.

Bouton « Exporter en YAML » (haut droite) → télécharge
`data/capabilities.yaml` pour commit/PR review.

## 21.6 Default policies récap

| Permission | Default | Override mechanism |
|------------|---------|---------------------|
| `read` | **ALLOW** (open par défaut) | Row `enabled=false` pour bloquer une combinaison |
| `react` | N/A v1 (futur P21.X) | — |
| `write_back` | **DENY** (closed par défaut) | Row `enabled=true` explicite |

Justification du double standard : `read` est **non-modifiant** (B
regarde, A ne sait pas / ne change pas). Ouvrir par défaut maximise la
valeur sans risque. `write_back` est **modifiant** (B influence le
comportement de A) — exige une décision explicite de l'opérateur.

## 21.7 Audit trail

Chaque run d'agent log dans `agent_runs.capabilities_consumed` :
```json
[
  {"capability_id": 7, "object": "EmailBot", "items_consumed": 12},
  {"capability_id": 9, "object": "FinanceBot", "items_consumed": 3}
]
```

Chaque write-back log dans `agent_runs.output_summary` ET crée un
`memory_item` avec `item_type='advice.*'` traçable. Donc on peut
toujours répondre à « qui a recommandé quoi à qui, et quand ».

Vue de cet audit dans le Admin Panel : page **Câblage** > onglet
**Activité** (timeline des consume + write_back des 7 derniers jours).

## 21.8 Phasage P21.A → P21.C

| Sous-partie | Périmètre | Effort | Dépendances |
|-------------|-----------|--------|-------------|
| **P21.A** | Migration DB + `argos_ops/capabilities/loader.py` + `consume_capabilities()` (read seulement) + tests | ~0.5 session | P20.A |
| **P21.B** | Frontend Admin Panel page Câblage (matrice + drawer édition + export YAML) | ~1 session | P21.A + P16.B |
| **P21.C** | `write_back()` + cycle detection + breaker `capability_loop_detected` | ~0.5 session | P21.A + P15 |

P21.A débloque immédiatement le cas TargetSpotter ↔ EmailBot et
Compta ↔ FinanceBot (les exemples du fondateur). P21.C ajoute la
mécanique BudgetWatcher ↔ AdBot (write-back).

## 21.9 Bénéfices concrets

| Combinaison | Capability | Bénéfice |
|-------------|------------|----------|
| TargetSpotter ← EmailBot | `read` filtré sur `email_inbound + lead-chaud` | Spotter enrichit son backlog en temps quasi-réel sans recoder son input pipeline |
| Compta ← FinanceBot | `read` filtré sur `stripe_event, dunning_sent` | Vision comptable cohérente sans dupliquer la logique Stripe |
| BudgetWatcher ← AdBot, TargetSpotter | `read` cross-agent | Décision budget informée par perf ads + volume leads |
| AdBot ← BudgetWatcher | `write_back` sur `advice.budget_adjust` | Budget agile sans intervention humaine quotidienne (mais opérateur valide les advice via Admin Panel) |
| claude-judge ← * | `read` sur tous les drafts | Détection drift de ton/factualité cross-agent |
| OutboundBot ← TargetSpotter | `read` sur `lead_qualified` | Pipeline lead → outbound automatique (toujours pull, B = OutboundBot run au cron) |

## 21.10 Anti-patterns à éviter

- ❌ Implémenter le mode `react` (push trigger) en v1 — risques cascade
  non maîtrisés, viole la décision Q5 (pull confirmé)
- ❌ Ouvrir `write_back` par défaut — un agent malformé pourrait
  influencer le comportement de tous les autres
- ❌ Skip la cycle detection au moment du save — un cycle créé en UI
  doit être refusé avant insertion, pas découvert à runtime
- ❌ Ne pas tracer `capabilities_consumed` dans `agent_runs` — perd
  l'audit, impossible de répondre à « qui a tiré quoi ce jour-là »
- ❌ Stocker la config uniquement en DB sans export YAML — pas de
  trace git, pas de rollback propre en cas de mauvais setup
- ❌ Permettre à un agent de se write-back lui-même (auto-influence) —
  contrainte CHECK SQL `subject_agent <> object_agent`

✅ **Done quand** :
- P21.A : table créée, `consume_capabilities()` câblé dans 2 agents
  existants en démo (ex Compta ← FinanceBot), tests passent
- P21.B : page Câblage live dans l'Admin Panel, matrice éditable,
  YAML export fonctionnel
- P21.C : 1 chaîne write-back testée (BudgetWatcher → AdBot), cycle
  detection refuse un cycle volontaire, breaker câblé

---

# Annexe A — Dépendances entre parties

```
P0 → P1 → P2 → P3 → P4
                P3 → P5 → P6 → P14 → P15 → P16
                P3 → P7
                P3 → P11 → P9 → P10
                P3 → P12 (besoin P14, P15)
                P3 → P13 (besoin P5, P14, P15, P17)
                P3 → P20.A → P20.B → {P20.C, P20.D}
                P20.A prérequis non-bloquant de P9-full, P12.B, P13
P17 en parallèle de tout
P18 mise à jour à chaque création de skill
P19 démarre quand P4 existe
P20 démarre quand P3+P6+P14+P15 sont done (✅ tous done au 2026-05-15)
P21 hard prerequisite : P20.A (DB memory_items doit exister)
P21.B prerequisite : P16.B (Admin Panel control mode)
```

# Annexe B — Ordre recommandé d'exécution

Si le fondateur doit choisir 1 partie par jour pendant les 4 premières semaines :

| Jour | Partie | Sprint |
|------|--------|--------|
| 1 | P0 | — |
| 2 | P1 | — |
| 3-4 | P2 | Sprint 0 |
| 5-6 | P3 | Sprint 0 |
| 7 | P4 | Sprint 0 |
| 8 | P14 (juge) | Sprint 4 anticipé |
| 9 | P15 (breakers) | Sprint 4 anticipé |
| 10-11 | P5 (EmailBot) | Sprint 1 |
| 12 | P6 (SupportBot) | Sprint 1 |
| 13 | P7 (FinanceBot) | Sprint 1 |
| 14 | **P16.A — Admin Panel MVP (read-only)** | Sprint 1 |
| 15 | P17 (compliance) | Continu |
| ~~16-18~~ | ~~P8 (ChatBot widget)~~ — **cancelled D-019** | — |
| 19-20 | P11 (connecteurs sociaux) | Sprint 2 |
| 21-22 | P9 (ContentBot) | Sprint 2 |
| 23-24 | P10 (SEOBot) | Sprint 2 |
| 25 | **P16.B — Admin Panel Control (toggle, intensity)** | Sprint 2 |
| 26-27 | P12 (AdBot shadow mode) | Sprint 3 |
| 28-29 | P13 (OutboundBot) | Sprint 3 |
| 30 | **P16.C — Admin Panel Escalations queue** | Sprint 3 |
| 31 | **P16.D — Admin Panel KB editor + 2FA** | Sprint 4 |
| 32-33 | P19 (observabilité) | Continu |
| 34 | **P20.A — Argos Memory foundation** (DB + archive + hook BaseAgent) | Sprint 2 prereq |
| 35 | **P20.B — Argos Memory semantic search** (skill `argos-memory`) | Sprint 2 prereq |
| 36 | **P20.C — Argos Memory curator** (insights hebdo) | Sprint 2+ |
| 37 | **P20.D — Argos Memory auditor + GC** (`/memory-gc`) | Sprint 2+ |
| 38 | **P21.A — Capabilities foundation** (table + `consume_capabilities()` read) | Sprint 2+ (après P20.A) |
| 39 | **P21.B — Capabilities Admin Panel page** (matrice Câblage + export YAML) | Sprint 2+ (après P21.A + P16.B) |
| 40 | **P21.C — Capabilities write-back + cycle detection** | Sprint 2+ (après P21.A + P15) |

Nota : dans la cadence du fondateur (10-12 sessions/jour), ces 30 jours de plan
peuvent se compresser à ~3-5 jours réels.

**Argos Memory (P20)** : si l'objectif est de livrer ContentBot full (P9),
AdBot live (P12.B) ou OutboundBot (P13), il est fortement recommandé de
faire P20.A + P20.B **avant**, pour que ces agents naissent déjà
"mémoire-aware" plutôt que d'être rétro-câblés.

---

# Annexe D — Catalogue cible : 12 services × 86 bots

> **Source unique de l'état d'avancement** (depuis 2026-05-23).
> `CLAUDE.md` ne porte plus de section "État d'avancement" et
> `docs/PROGRESS.md` est supprimé. Toute mise à jour de statut bot se fait
> ici via les checkboxes ci-dessous.

## Récap chiffres (auto-maintenu à chaque livraison)

- ✅ **83 agents Python actifs** + **1 skill (ClaudeJudge)** = **84 livrés**
- 🟡 **1 partiel** (OutboundBot — P13.A shadow + P22.H stage mode, live attend domaine secondaire D-023)
- ⬜ **9 roadmap** (CapabilityRouter bloqué sur P21.A, MemoryCurator bloqué sur P20.A, **6 PlatformWriters** + **EditorialBot** prévus Sprint B contenu multi-plateforme)
- **Total cible : 86 bots** répartis sur 12 services *(dépassé via 7 upgrades skills/shadow → agent Python full lors du méta-sprint P22.D-I, étendu en 2026-06 avec la flotte writers multi-plateformes).*

Légende :
- `[x] ✅` — livré et actif (Python agent en cron OU skill réutilisable)
- `[~] 🟡` — partiel (skill / shadow mode livré, pas encore d'agent Python en cron)
- `[ ] ⬜` — roadmap

## Principe d'organisation

Chaque bot = **1 tâche atomique = 1 poste-clé équivalent grande entreprise**.
La flotte est structurée comme une org-chart : la Direction donne les
directives, les pôles métier exécutent, Meta-Ops orchestre la flotte.

**Catalogue technique** :
[`argos_ops/ops_dashboard/frontend/src/lib/agentCatalog.ts`](../argos_ops/ops_dashboard/frontend/src/lib/agentCatalog.ts).
Le frontend Admin Panel range les bots par service avec status pill.

## Les 12 services

### 1. Direction & Stratégie
*Donne les directives et priorise les autres bots.*

- [x] ✅ **StrategyBot** · VP Stratégie · Synthèse hebdo KPIs critiques + alerte drift OKR. *P22.E livré 2026-05-23.*
- [x] ✅ **OKRTracker** · Chief of Staff · Réalisé vs objectifs trimestriels par pôle. *P22.E livré 2026-05-23.*
- [x] ✅ **BoardReporter** · Investor Relations · Board pack mensuel (MRR / burn / runway / NRR). *P22.E livré 2026-05-23.*
- [x] ✅ **DecisionLogger** · Knowledge Steward · Capture décisions structurantes → DECISIONS.md. *P22.E livré 2026-05-23.*

### 2. Finance & Trésorerie
*Comptabilité, budget, trésorerie, dunning.*

- [x] ✅ **FinanceBot** · Contrôleur financier · Sync Stripe + dunning J+3/J+7/J+15. *P7 livré 2026-05-09.*
- [x] ✅ **InvoicePredictor** · Trésorier · Forecast cash flow 30/60/90j depuis Stripe subs actives. *P22.F livré 2026-05-23.*
- [x] ✅ **ExpenseAuditor** · Contrôleur de gestion · Audit CSV Qonto + anomalies (outliers / doublons / nouveaux vendors). *P22.F livré 2026-05-23.*
- [x] ✅ **TaxBot** · Fiscaliste · TVA CA3 mensuelle + IS prévisionnel (draft markdown). *P22.F livré 2026-05-23.*
- [x] ✅ **ReconcileBot** · Comptable · Rapproche Stripe payouts ↔ crédits Qonto. *P22.F livré 2026-05-23.*
- [x] ✅ **BurnRateMonitor** · CFO adjoint · Alerte burn > seuil ou runway < 9 mois. *P22.F livré 2026-05-23.*
- [x] ✅ **VendorContractWatcher** · Achats · Renouvellements fournisseurs avant tacite reconduction. *P22.F livré 2026-05-23.*

### 3. Sales / Commercial
*Ramener des clients (cible primaire + secondaire).*

- [~] 🟡 **OutboundBot** · SDR Cold Email · Séquence cold email 5 touches (D+0/3/7/14/30). *P13.A shadow done 2026-05-15. P22.H stage mode livré 2026-05-23 (OutboundSender — sends → self pour audit). Live mode P13.B activable dès domaine secondaire warmé-up (cf. D-023).*
- [x] ✅ **LeadEnricher** · Lead Intel · Enrichit lead BtoB depuis nom + domaine. *P18 skill livré 2026-05-14. Agent Python batch livré 2026-05-23 (P22.H Sprint 3).*
- [x] ✅ **ProspectMiner** · Sourcer · Trouve leads ICP via sources publiques (annonces, levées). *P22.H Sprint 3 livré 2026-05-23.*
- [x] ✅ **IntentSignalsBot** · Lead Gen Lead · Capte signaux d'achat (breaches publics, embauches CISO). *P22.H Sprint 3 livré 2026-05-23.*
- [x] ✅ **MeetingBooker** · Sales Ops · Confirme RDV démo + rappels J-1 / H-1. *P22.H Sprint 3 livré 2026-05-23.*
- [x] ✅ **DemoFollowupBot** · Account Executive · Mail récap post-démo + next steps. *P22.H Sprint 3 livré 2026-05-23.*
- [x] ✅ **ProposalBot** · Sales Engineer · Devis personnalisé depuis template. *P22.H Sprint 3 livré 2026-05-23.*
- [x] ✅ **ContractGenerator** · Sales Legal · CGV / MSA depuis template + variables client. *P22.H Sprint 3 livré 2026-05-23.*
- [x] ✅ **DealRiskScorer** · Sales Manager · Score pipe + flag deals stalled > 14j. *P22.H Sprint 3 livré 2026-05-23.*

### 4. Marketing & Growth
*Top funnel : SEO, ads, social, contenu, growth.*

- [x] ✅ **SEOBot** · SEO Strategist · Briefs blog SEO structurés depuis KB. *P10-MVP livré 2026-05-12.*
- [x] ✅ **ContentBot** · Content Manager · 2-5 posts/jour LinkedIn / Mastodon. *P22i livré 2026-05-23 (full agent Python + connecteurs P11). Shadow tant que LinkedIn / Mastodon tokens absents (D-024 / D-025).*
- [ ] ⬜ **LinkedInWriter** · Content Writer LinkedIn · Drafte un post LinkedIn long-form B2B technique depuis topic + KB. Ne poste pas — transmet à ContentBot via `data/content/drafts/`. *Sprint B prévu (split de `content-writer`). Skill scaffoldé via `skill-creator`.*
- [ ] ⬜ **MastodonWriter** · Content Writer Mastodon · Drafte un toot court tone infosec community (#infosec, #bugbounty) depuis topic + KB. Ne poste pas. *Sprint B prévu (split de `content-writer`). Skill scaffoldé via `skill-creator`.*
- [ ] ⬜ **MetaWriter** · Content Writer Facebook · Drafte un post Facebook Page pour persona TPE/PME non-technique (anti-FUD, vocab grand public, CTA tier bas Argos). Ne poste pas. *Sprint B prévu — persona à part (cf. memo project_metawriter_smb_persona). Skill scaffoldé via `skill-creator`.*
- [ ] ⬜ **XWriter** · Content Writer X · Drafte un tweet 280 chars / hook punchy / angle viral cyber depuis topic + KB. Ne poste pas. *Sprint B prévu — connecteur Python + API cost à arbitrer ($200/mois Basic ou Free 1500/mois). Skill scaffoldé via `skill-creator`.*
- [ ] ⬜ **BlueskyWriter** · Content Writer Bluesky · Drafte un post Bluesky 300 chars tone tech early adopters depuis topic + KB. Ne poste pas. *Sprint B prévu — quick win (API AT Protocol gratuite illimitée). Skill scaffoldé via `skill-creator`.*
- [ ] ⬜ **TruthSocialWriter** · Content Writer Truth Social · Drafte un post Truth Social (audience US conservative, API forked Mastodon) depuis topic + KB. Ne poste pas. *Sprint B prévu — demande d'accès API à soumettre. Skill scaffoldé via `skill-creator`.*
- [ ] ⬜ **EditorialBot** · Editor-in-Chief · Lit TrendSpotter le matin, choisit angle + canal, dispatch automatiquement au writer adapté. Orchestre uniquement, ne crée ni ne publie de contenu lui-même. *Sprint B+1 — activable après 3 sem de drafts validés (sinon orchestration dans le vide).*
- [x] ✅ **AdBot** · Paid Acquisition · Pilotage Google / Meta / LinkedIn Ads. *P22i livré 2026-05-23 (live mode P12.B). Shadow tant que ADS_LIVE_MODE=false + budget pub validé (D-026).*
- [x] ✅ **TrendSpotter** · Trend Analyst · Tendances cyber → SEOBot / ContentBot. *P22i livré 2026-05-23.*
- [x] ✅ **NewsletterBot** · Email Marketing · Newsletter mensuelle depuis blog + actu cyber. *P22i livré 2026-05-23.*
- [x] ✅ **SocialAnalytics** · Community Analytics · Reporting hebdo engagement par canal. *P22i livré 2026-05-23.*
- [~] 🗑️ **BacklinkOutreach** · SEO Off-page · Prospecte sites cyber pour échanges de liens. *P22i livré 2026-05-23.* **Retiré par [D-030](DECISIONS.md#d-030) le 2026-06-13 (template/stub sans valeur).**
- [x] ✅ **KeywordRadar** · SEO Specialist · Surveille positions SERP + opportunités longue traîne. *P22i livré 2026-05-23.*
- [x] ✅ **LandingOptimizer** · CRO Specialist · Analyse heatmaps + propose variantes A/B. *P22i livré 2026-05-23.*
- [~] 🗑️ **WebinarPromoter** · Field Marketing · Promote webinar + replay edit. *P22i livré 2026-05-23.* **Retiré par [D-030](DECISIONS.md#d-030) le 2026-06-13 (template/stub sans valeur).**
- [x] ✅ **TestimonialHunter** · Customer Marketing · Verbatims post-NPS positif. *P22i livré 2026-05-23.*
- [~] 🗑️ **CaseStudyDrafter** · Content Senior · Case study depuis compte référence. *P22i livré 2026-05-23.* **Retiré par [D-030](DECISIONS.md#d-030) le 2026-06-13 (template/stub sans valeur).**

### 5. Customer Success & Support
*Onboarding, rétention, support technique.*

- [x] ✅ **SupportBot** · Support Tier 1 · Réponses Tier 1 RAG sur KB Argos. *P6 livré 2026-05-09.*
- [x] ✅ **ReviewBot** · Customer Advocacy · Sollicite avis G2 / Capterra / Google J+30. *P22.G livré 2026-05-23 (promoteurs NPS ≥ 9 uniquement).*
- [x] ✅ **ChurnPredictor** · Retention Manager · Détecte signaux pré-churn. *P22.G livré 2026-05-23 (score 0-100 + snapshot quotidien).*
- [x] ✅ **OnboardingBot** · CSM Onboarding · Checklist J+0 / J+7 / J+30 post-signup. *P22.G livré 2026-05-23 (drafts humain-in-the-loop).*
- [x] ✅ **HealthScoreBot** · CS Ops · Score santé compte (usage + tickets + NPS). *P22.G livré 2026-05-23 (heuristiques explicites, snapshot quotidien).*
- [x] ✅ **KBUpdater** · Knowledge Manager · Détecte gaps KB depuis tickets → drafte article. *P22.G livré 2026-05-23 (clustering mots-clés, audit kb-rag + claude-judge).*
- [x] ✅ **NPSCollector** · Voice of Customer · NPS post-onboarding + à chaque renew. *P22.G livré 2026-05-23 (J+14 onboarding / J+21 renew).*
- [x] ✅ **UpsellSpotter** · Account Growth · Repère comptes prêts upsell. *P22.G livré 2026-05-23 (usage ≥ 80% quota plan).*
- [x] ✅ **EscalationRouter** · Support Lead · Trie tickets P0 / P1 / P2 selon SLA. *P22.G livré 2026-05-23 (SLA breach détecté, snapshot triage).*

### 6. Produit & R&D
*Roadmap, release notes, feedback, discovery.*

- [x] ✅ **ChangelogBot** · Product Marketing · Changelog mensuel depuis commits mergés. *P22.G livré 2026-05-23 (conventional commits + sections keepachangelog).*
- [x] ✅ **ReleaseNotesBot** · Product Manager · Release notes user-friendly par feature. *P22.G livré 2026-05-23 (depuis spec.yaml, ton anti-jargon).*
- [x] ✅ **FeedbackAggregator** · Product Discovery · Agrège demandes clients par thème. *P22.G livré 2026-05-23 (clustering exact, digest Markdown).*
- [x] ✅ **RoadmapPublisher** · Head of Product · Publie roadmap publique depuis cette annexe D. *P22.G livré 2026-05-23 (parser Annexe D, codes sprint retirés).*
- [x] ✅ **BugTriageBot** · QA Lead · Trie issues GitHub par sévérité + assigne label. *P22.G livré 2026-05-23 (mots-clés P0/P1/P2, read-only).*

### 7. Tech / SRE / Sécurité IT
*Uptime, secrets, dépendances, backups.*

- [x] ✅ **UptimeMonitor** · SRE · Ping endpoints publics, alerte si down > 60s. *P22.C livré 2026-05-23.*
- [x] ✅ **DependencyAuditor** · AppSec · Scan deps + alerte CVE (uv + osv.dev). *P22.C livré 2026-05-23.*
- [x] ✅ **BackupVerifier** · DevOps · Vérifie backup Postgres récent < 24h. *P22.C livré 2026-05-23.*
- [x] ✅ **SSLExpirer** · IT Security · Alerte certif SSL expirant < 30j. *P22.C livré 2026-05-23.*
- [x] ✅ **SecretRotator** · Security Engineer · Alerte secrets > 90j. *P22.C livré 2026-05-23.*
- [x] ✅ **LogAnomalyDetector** *(fusionné dans FleetWatchdog — D-031)* · SRE Observability · Pics d'erreurs dans logs serveur. *P22.D livré 2026-05-23, fusionné 2026-06-13.*
- [x] ✅ **DNSGuard** · IT Network · Changements DNS suspects sur omnividens.fr. *P22.D livré 2026-05-23.*
- [x] ✅ **CIFlakeTracker** · DevOps Lead · Tests CI flaky → issue auto. *P22.D livré 2026-05-23.*

### 8. Veille & Threat Intelligence
*Concurrence, breaches, régulation, CVE.*

- [x] ✅ **CompetitorWatcher** · Competitive Intel · Scrape hebdo features / pricing concurrents. *P22.D livré 2026-05-23.*
- [x] ✅ **BreachWatcher** · Threat Intel · Breaches publics (HIBP, CERT-FR) → leads chauds. *P22.D livré 2026-05-23.*
- [x] ✅ **RegulatoryWatcher** · Compliance Watch · Évolutions RGPD / AI Act / NIS2 / DORA. *P22.D livré 2026-05-23.*
- [x] ✅ **CVEMonitor** · Threat Intel · CVE critiques sur stack clients déclarée. *P22.D livré 2026-05-23.*
- [x] ✅ **DarkWebMonitor** · Threat Intel Senior · Mentions domaines clients sur dark web. *P22.D livré 2026-05-23 (MVP HIBP).*
- [~] 🗑️ **BountyRadar** · Bug Bounty Manager · Programmes bounty pertinents à positionner. *P22.D livré 2026-05-23.* **Retiré par [D-030](DECISIONS.md#d-030) le 2026-06-13 (template/stub sans valeur).**

### 9. Juridique & Compliance
*RGPD, AI Act, Bloctel, contrats clients.*

- [x] ✅ **RGPDAuditor** · DPO · Registre traitements + alerte traitement non documenté. *P22.E livré 2026-05-23.*
- [x] ✅ **AIActComplianceBot** · AI Compliance Officer · Vérifie chaque agent IA vs catégorie AI Act. *P22.E livré 2026-05-23.*
- [x] ✅ **BloctelGuard** · Compliance Bloctel · Check leads outbound vs liste opposition. *P22.E livré 2026-05-23.*
- [x] ✅ **ContractDeadlineBot** · Legal Ops · Renouvellements contrats clients (anniv-60j). *P22.E livré 2026-05-23.*
- [x] ✅ **IncidentLogger** · RSSI · Log incidents sec internes + post-mortem template. *P22.E livré 2026-05-23.*

### 10. Communication
*RP, presse, comms de crise, brand consistency.*

- [x] ✅ **EmailBot** · Standardiste Inbox · Pull IMAP 15 min + ingestion CRM + notif Discord. *P5 livré 2026-05-09.*
- [x] ✅ **ReplyBot** · Community Manager · Réponses mentions LinkedIn / Mastodon (humain-validé). *P22i livré 2026-05-23.*
- [x] ✅ **PressMonitor** · Veille presse · Mentions Argos / Omnividens / SecHunter sur le web. *P22i livré 2026-05-23.*
- [~] 🗑️ **PressReleaseDrafter** · RP Manager · Communiqué de presse annonces produit / finance. *P22i livré 2026-05-23.* **Retiré par [D-030](DECISIONS.md#d-030) le 2026-06-13 (template/stub sans valeur).**
- [x] ✅ **MediaListBuilder** · Attaché de presse · DB journalistes / médias cyber pertinents. *P22i livré 2026-05-23.*
- [~] 🗑️ **CrisisCommBot** · Comm de crise · Réponse type prête en cas d'incident public. *P22i livré 2026-05-23.* **Retiré par [D-030](DECISIONS.md#d-030) le 2026-06-13 (template/stub sans valeur).**
- [~] 🗑️ **SpokespersonPrep** · Media Training · Q&A briefs interviews founder. *P22i livré 2026-05-23.* **Retiré par [D-030](DECISIONS.md#d-030) le 2026-06-13 (template/stub sans valeur).**
- [x] ✅ **BrandGuardBot** · Brand Manager · Cohérence ton / tagline / signature sur drafts sortants. *P22i livré 2026-05-23.*

### 11. Documentation & Knowledge interne
*Maintenance des docs techniques internes.*

- [x] ✅ **DocLinter** · Technical Writer · Liens internes morts + anchors morts dans `docs/`, `README.md`, `CLAUDE.md`. *P22.F livré 2026-05-23.*
- [x] ✅ **DiagramGenerator** · Tech Doc · Flowchart Mermaid depuis spec YAML. *P22.F livré 2026-05-23.*
- [x] ✅ **ADRWriter** · Tech Lead · ADR MADR léger depuis input structuré, idempotent par slug. *P22.F livré 2026-05-23.*

### 12. Meta-Ops
*Bots qui gèrent les bots.*

- [x] ✅ **DigestBuilder** · Reporting Officer · Récap quotidien Discord 8h Paris. *P4 livré 2026-05-08.*
- [x] ✅ **ClaudeJudge** *(skill)* · QA des bots · Audite outputs (factual / tone / legal). *P14 livré 2026-05-14.*
- [x] ✅ **OrchestratorBot** · Chef de fleet · Route / priorise jobs entre bots (dry-run par défaut). *P22.B livré 2026-05-23.*
- [x] ✅ **FleetWatchdog** · SRE unifié de la flotte · Fusionne santé/freshness + perf P50/P95 + triage erreurs + anomalies de volume en 1 passe sur `agent_runs` (1 embed multi-sections, cron 6h). *Fusion Axe 3.2 / D-031, 2026-06-13.*
- [x] ✅ **BotHealthBot** *(fusionné dans FleetWatchdog — D-031)* · SRE de la flotte · Surveille uptime + dernier run par agent. *P22.B livré 2026-05-23, fusionné 2026-06-13.*
- [x] ✅ **BotPerfAnalyzer** *(fusionné dans FleetWatchdog — D-031)* · Performance Engineer · Durée P50/P95 + taux d'erreur 7j vs baseline. *P22.C livré 2026-05-23, fusionné 2026-06-13.*
- [x] ✅ **ErrorTriageBot** *(fusionné dans FleetWatchdog — D-031)* · Bot Ops · Regroupe erreurs 24h par signature, alerte si ≥3 occurrences. *P22.C livré 2026-05-23, fusionné 2026-06-13.*
- [x] ✅ **KillSwitchOperator** · Safety Officer · Enforce breakers P15 + guide reset. *P22.C livré 2026-05-23.*
- [x] ✅ **BotConfigManager** · Config Ops · Diff agent_config DB vs baseline.yaml, alerte drifts. *P22.C livré 2026-05-23.*
- [ ] ⬜ **CapabilityRouter** · Capability Manager · Route demandes vers bot qualifié (Capabilities P21). *Bloqué sur P21.A.*
- [ ] ⬜ **MemoryCurator** · Memory Steward · Nettoie / dédup Argos Memory partagée. *Bloqué sur P20.A.*

---

## Critère de priorisation

Un slot roadmap passe en partie active **P-numérotée** quand :
- le founder a une vraie demande pour cet agent, OU
- un signal business le justifie (ex : ReviewBot prioritaire à 20+ clients,
  ChurnPredictor à 50+ clients).

## Anti-pattern : ne pas créer ces bots par anticipation

YAGNI strict. Le catalogue 79 bots ne signifie pas « 79 bots à coder
demain ». Il sert à :

1. Donner au founder une **vision claire du champ d'action futur**.
2. **Cadrer les futures décisions** (DECISIONS.md) en ayant un nom canonique
   et un poste équivalent quand un agent émerge.
3. Permettre à Claude Code de **réutiliser le catalogue** quand il propose
   un nouveau bot — pas de réinvention, pas de doublons.

## Sprints pressentis (ordre d'attaque conseillé)

- **Sprint 1** ✅ : Meta-Ops core (OrchestratorBot + BotHealthBot) — done P22.B.
- **Sprint 2** 🟡 partiel : reste Meta-Ops (BotPerfAnalyzer + ErrorTriageBot
  + KillSwitchOperator + BotConfigManager) done P22.C. Toujours en attente :
  P20 (Argos Memory), P21 (Capabilities), CapabilityRouter, MemoryCurator.
- **Sprint 3** : Sales (ProspectMiner, IntentSignalsBot, MeetingBooker,
  DemoFollowupBot) — ramener des clients.
- **Sprint 4** 🟡 partiel : Tech / SRE (Uptime, DepAudit, Backup, SSL,
  Secret) done P22.C. Reste LogAnomaly, DNS, CIFlake.
- **Sprint 5** : Communication (PressMonitor, PressRelease, BrandGuard).
- **Sprint 6** : Veille Intel (BreachWatcher, RegulatoryWatcher).
- **Sprint 7** : CS (Onboarding, HealthScore, KBUpdater).
- **Sprint 8** : Compliance (RGPDAuditor, AIActComplianceBot, BloctelGuard).
- **Sprint 9** : Direction (StrategyBot, OKRTracker, BoardReporter).
- **Sprint 10** : Finance avancé (ExpenseAuditor, TaxBot, etc.).
- **Sprint 11** : Produit (Changelog, ReleaseNotes, Feedback, BugTriage).
- **Sprint 12** : Marketing avancé (Newsletter, Backlink, Keyword, etc.).
- **Sprint 13** : Documentation (DocLinter, DiagramGenerator, ADRWriter).

## Procédure de mise à jour de cette annexe

À chaque livraison d'un bot, le founder (ou Claude Code en fin de session) :
1. Change `[ ] ⬜` en `[x] ✅` (ou `[~] 🟡` si partiel) sur la ligne du bot.
2. Ajoute la date entre `*italique*` à la fin de la ligne (ex : *P22.C livré 2026-05-23.*).
3. Met à jour le compteur en tête (« Récap chiffres »).
4. Marque le Sprint correspondant ✅ ou 🟡 dans la section « Sprints pressentis » si applicable.

**Ne PAS** mettre à jour CLAUDE.md ni recréer un PROGRESS.md.
**Ne PAS** dupliquer cette annexe ailleurs — elle est la source unique.

---

# Annexe C — Anti-patterns à éviter

- ❌ Mettre Claude Code en charge du chat live client : abonnement pas fait pour ça,
  rate limits, on bascule la cadence cron au lieu d'utiliser une API tierce (D-017)
- ❌ Outbound depuis le domaine principal : préserver la réputation `omnividens.fr`
- ❌ Skip l'agent-juge sur 1 agent « parce qu'on est pressé » : c'est lui qui rend tout
  le système safe à déléguer
- ❌ Cron sans logging dans `agent_runs` : impossible de débugger après coup
- ❌ Pas de breakers sur les agents qui dépensent (Ads, OutboundBot) : risque budget out
  of control
- ❌ Faux avis ou faux témoignages : illégal, perte de réputation immédiate
- ❌ Cold call BtoC sans Bloctel : amende CNIL jusqu'à 75 k€

---

# Fin du plan

Ce document est conçu pour être consommé partie par partie par des sessions Claude Code
indépendantes. Mettre à jour la table de progression de la Partie 18 à chaque skill créé
et la table d'avancement du `CLAUDE.md` projet `argos-ops` à chaque partie complétée.
