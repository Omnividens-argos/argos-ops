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
| 8 | Chatbot widget site (Claude Code Pro Max + queue Redis, D-017) | Sprint 1 | `frontend-design`, `skill-creator` |
| 9 | ContentBot multi-canal | Sprint 2 | `skill-creator` |
| 10 | SEOBot stratégie + briefs | Sprint 2 | `skill-creator` |
| 11 | Connecteurs sociaux (LinkedIn / X / Reddit) | Sprint 2 | — |
| 12 | AdBot — pilotage Google/Meta/LinkedIn Ads | Sprint 3 | `skill-creator` |
| 13 | OutboundBot — cold email volume modéré | Sprint 3 | `skill-creator` |
| 14 | Agent-juge Tier 1 (supervision IA) | Sprint 4 | `skill-creator` |
| 15 | Circuit breakers et kill switches | Sprint 4 | — |
| 16 | Admin Control Panel (start/stop agents, throttle, KPIs, KB editor) | Sprints 1→4 (phasé) | `ui-ux-pro-max` + `frontend-design` (obligatoires) |
| 17 | Conformité RGPD / AI Act / Bloctel | Continu | — |
| 18 | Inventaire des skills à créer | Continu | `skill-creator` |
| 19 | Maintenance et observabilité | Continu | — |

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
- Conversion semi-auto (chatbot + email + démo)
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
   ContentBot        ChatBot             SupportBot
   SEOBot            EmailBot in         CSMBot
   AdBot             DemoBot (P2)        FinanceBot
   OutboundBot       CallerBot (P2)      AnalyticsBot
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
  (Ops Dashboard, Partie 16) et un éventuel `chat.omnividens.fr` → endpoint chat widget
  (Partie 8). Ces blocs Caddy sont à ajouter dans le container `sechunter-caddy-1`.
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
| Cache + queue | Redis (cache + `inbox_pending` queue webhooks) | 0 € | serveur SecHunter |
| **LLM chat live** | **Claude Code Pro Max + queue Redis pull-based** (D-017) | **0 € (forfait Pro Max)** | runtime ordi |
| **LLM agents (tous)** | **Claude Code Pro Max via slash commands** (D-017) | **0 € (forfait Pro Max)** | runtime ordi |
| **Embeddings KB** | **`fastembed` + `multilingual-e5-base`** (CPU local) (D-017) | **0 € forever** | ordi fondateur |
| Email inbound | Gmail API + IMAP | 0 € | runtime ordi |
| Email outbound (volume modéré) | Gmail API (≤ 500/jour) | 0 € | runtime ordi |
| Social posting | API natives LinkedIn / Mastodon / Reddit (D-004 remplace X) | 0 € | runtime ordi |
| Ads pilotage | Google Ads / Meta / LinkedIn Marketing APIs | 0 € (budget pub à part) | runtime ordi |
| Webhook receivers | FastAPI + Caddy reverse proxy (`chat.omnividens.fr` etc.) | 0 € | serveur SecHunter |
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
- **Reddit Apps** : `r/script` app pour OAuth — 5 min (D-005 différé `P11-PREP`)
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
│   │   ├── reddit.py
│   │   ├── gmail.py
│   │   ├── stripe.py
│   │   ├── embeddings.py              # D-017 — fastembed multilingual-e5-base local
│   │   ├── google_ads.py
│   │   ├── meta_ads.py
│   │   └── umami.py                   # D-007 (analytics, INFRA-02)
│   ├── chat_widget/
│   │   ├── server.py                  # FastAPI receiver 24/7 (serveur SecHunter)
│   │   └── worker.py                  # Worker pull queue Redis (ordi fondateur, D-017)
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
  "praw>=7.7",                          # Reddit
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
  agent_name TEXT,                -- 'EmailBot' | 'ChatBot' | ...
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

🎯 **Objectif** : lire `contact@omnividens.fr` toutes les 15 min, classifier, drafter,
répondre auto si Tier 0/1, sinon mettre en file Tier 2.

🧱 **Prérequis** : Parties 2, 3, 4.

📦 **Livrables** :
- `.claude/commands/check-emails.md`
- Skill `gmail-ops` (lire, drafter, envoyer, marquer lu)
- Skill `email-classifier` (classifie en `lead_chaud` / `question_tech` / `sav` / `spam`)
- Cron `*/15 * * * *`

🛠️ **Skills à utiliser** :
- `skill-creator` pour formaliser `gmail-ops` (réutilisable par OutboundBot)
- `skill-creator` pour formaliser `email-classifier`

## 5.1 Pipeline

```
Boîte Gmail
     ↓
1. Pull emails non lus (Gmail API, label INBOX)
     ↓
2. Pour chaque email :
   - Classifier (skill email-classifier)
   - Lookup lead/company dans CRM, créer si absent
   - Insérer interaction direction='in'
   - Drafter réponse via Claude (RAG sur KB)
   - Soumettre à l'agent-juge Tier 1 (Partie 14)
     ↓
3. Si juge.score >= 80 :
   - Envoyer auto via Gmail API
   - Insérer interaction direction='out', judge_verdict='auto_send'
4. Si 50 <= score < 80 :
   - Drafter dans Gmail (label "À valider")
   - Notif Discord
   - judge_verdict='queued'
5. Si score < 50 :
   - Kill, log, pas d'envoi
   - judge_verdict='killed'
```

## 5.2 Garde-fous

- Ne jamais répondre à un email avec `noreply@` dans l'expéditeur
- Détecter les boucles (3 emails échangés en moins de 5 min → escalade Tier 2)
- Limite 50 réponses auto/jour pendant 1 mois (warm-up délivrabilité)

✅ **Done quand** : un email test envoyé à `contact@omnividens.fr` est traité en moins de
20 min, classifié correctement, une draft cohérente est créée, et l'interaction loggée.

---

# Partie 6 — SupportBot Tier 1 (RAG sur KB)

🎯 **Objectif** : répondre aux tickets simples (questions sur features, pricing, intégration)
en s'appuyant sur la KB pgvector.

🧱 **Prérequis** : Parties 3, 5.

📦 **Livrables** :
- `.claude/commands/run-support-tier1.md`
- Skill `kb-rag` (recherche similarité + assemblage contexte)
- Intégration EmailBot et ChatBot consomment ce skill

🛠️ **Skills à utiliser** :
- `skill-creator` pour `kb-rag` (réutilisable par EmailBot, ChatBot, ContentBot)

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

# Partie 8 — Chatbot widget site (Claude Code Pro Max + queue Redis)

🎯 **Objectif** : widget chat sur `omnividens.fr` qui répond aux visiteurs,
qualifie les leads, propose démo. **Réponse différée si l'ordi du fondateur
est éteint (D-017)** — la queue Redis absorbe les messages 24/7.

🧱 **Prérequis** : Parties 3, 6.

📦 **Livrables** :
- Endpoint FastAPI `argos_ops/chat_widget/server.py` (déployé sur **serveur
  SecHunter** — couche données, 24/7)
- Composant React intégré au frontend SecHunter (`sechunter/dashboard/frontend/`)
- Worker Python local `argos_ops/chat_widget/worker.py` lancé par cron sur
  l'ordi du fondateur (D-017) qui pull la queue Redis
- Stockage conversations dans `interactions`

🛠️ **Skills à utiliser** :
- `frontend-design` pour la conception visuelle du widget (apparence, animations,
  responsive, dark/light mode cohérent avec la landing)
- `skill-creator` pour formaliser le skill `chat-orchestrator` (qui orchestre
  KB-RAG + lead-scoring + booking)

## 8.1 Architecture (révisée par D-017)

```
[Visiteur omnividens.fr — n'importe quelle heure]
   ↓
[Widget React] ──── WebSocket / SSE ───► [FastAPI /chat]   ← serveur SecHunter, 24/7
                                              ↓
                                         LPUSH inbox_pending {message, session_id}   Redis
                                              ↓
                                         HTTP 202 Accepted (réponse différée)
                                              ↓
                                         Widget affiche « Argos rédige… »


[ORDI fondateur — quand allumé]
cron */1 * * * * → claude --print "/process-chat-inbox"   ← Claude Code Pro Max
                       ↓
                   BRPOP inbox_pending   Redis distant
                       ↓
                   Embed local (multilingual-e5-base) + similarity search KB pgvector
                       ↓
                   Skill chat-orchestrator (Claude inline) → réponse + BANT score
                       ↓
                   Insert interaction direction='in/out'    Postgres distant
                       ↓
                   Push réponse vers la session (websocket back / polling endpoint)
                       ↓
                   Si BANT >= 70 → propose Cal.com auto-booked
                       ↓
                   Si signal hot → escalade Discord (webhook)
```

## 8.2 Pourquoi Claude Code Pro Max et pas Gemini / API tierce ?

Décision figée par [D-017](DECISIONS.md#d-017--argos-ops-100--local-first--claude-code-pro-max--embeddings-open-source-z%C3%A9ro-api-llm-tierce) :

- **Pas d'API LLM tierce** dans Argos Ops — souveraineté donnée + cohérence
  avec la contrainte « 0 € de SaaS récurrent »
- **Claude Code Pro Max consomme l'abonnement** (forfait connu) — pas de
  quota free tier qui peut sauter (cf. blocage P3-M3 sur Gemini)
- **Trade-off accepté** : latence non-réelle-temps. Le widget affiche
  « Argos rédige… », le visiteur reçoit la réponse quand l'ordi du fondateur
  pull la queue (typiquement < 5 min en heures ouvrées, plus si nuit)
- **Acceptable au launch** pour le volume early stage (≤ 100 chats/jour).
  Quand le coût d'opportunité (visiteurs qui décrochent en attendant)
  dépasse le coût d'un Mac mini / Pi 5 dédié 24/7 → on bascule sur ce relai

## 8.3 Booking démo

Pas de Cal.com payant : un simple lien Calendly free tier OU `cal.com` self-host. Le bot
propose 3 créneaux disponibles, le lead clique → booking Google Calendar du fondateur.

✅ **Done quand** : un visiteur sur `omnividens.fr` peut poser une question, voir un état
« Argos rédige… », recevoir une réponse (en heures ouvrées : < 5 min ; hors heures
ouvrées : différé jusqu'au réveil de l'ordi), et réserver un créneau qui apparaît dans le
Calendar du fondateur.

---

# Partie 9 — ContentBot multi-canal

🎯 **Objectif** : 2-5 posts/jour sur LinkedIn / X / Reddit / Mastodon, ton adapté à chaque
plateforme, sujets pilotés par SEOBot (Partie 10).

🧱 **Prérequis** : Parties 3, 11 (connecteurs sociaux).

📦 **Livrables** :
- `.claude/commands/run-content-bot.md`
- Skill `content-writer` (génère le contenu adapté à un canal donné)
- Skill `content-scheduler` (poste à l'heure optimale par canal)

🛠️ **Skills à utiliser** :
- `skill-creator` pour `content-writer`
- `skill-creator` pour `content-scheduler`

## 9.1 Logique quotidienne

1. Lire le calendrier éditorial dans une nouvelle table `editorial_calendar`
   (rempli par SEOBot la veille)
2. Pour chaque slot du jour :
   - Choisir le canal (LinkedIn / X / Reddit r/netsec / Mastodon infosec)
   - Générer le post via skill `content-writer` avec contraintes du canal
     (LinkedIn 1300-2000 chars, X 280, Reddit longform, Mastodon 500)
   - Soumettre à l'agent-juge Tier 1
   - Publier via skill `content-scheduler` à l'heure optimale par canal
3. Logger dans `interactions` avec `agent_name='ContentBot'`

## 9.2 Anti-spam Reddit

Reddit ban hard les comptes promo. Règle 9:1 : publier 9 contributions utiles non
promo pour chaque post promo. ContentBot doit comprendre cette règle (codée dur dans
le prompt système) — sinon ban du compte = perte du canal.

✅ **Done quand** : 5 posts publiés sur 24 h sur 4 canaux, 0 bannissement, engagement
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
  free, Reddit r/cybersecurity questions, KeywordTool free
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

# Partie 11 — Connecteurs sociaux (LinkedIn / X / Reddit)

🎯 **Objectif** : modules Python `argos_ops/integrations/` testés, OAuth qui marche,
post & lecture engagement automatisés.

🧱 **Prérequis** : Partie 1 (comptes API créés).

📦 **Livrables** :
- `argos_ops/integrations/linkedin.py` (publish, get_engagement, list_posts)
- `argos_ops/integrations/twitter.py` (idem)
- `argos_ops/integrations/reddit.py` (idem + filtre subreddit rules)
- Tests d'intégration `tests/integrations/` avec cassettes vcrpy

## 11.1 Particularités

- **LinkedIn** : auth la plus complexe, refresh token long-lived, API rate limit strict
  (100 calls/jour pour profil personnel sans Marketing Developer Platform)
- **X / Twitter** : Free tier limite à 1500 posts/mois, lecture timeline payante
- **Reddit** : OAuth simple, lecture libre, posting limité par subreddit karma

## 11.2 Pas de skill-creator ici

Pure plomberie HTTP, mieux vaut du Python testé que des skills.

✅ **Done quand** : `python -m argos_ops.integrations.linkedin --test-post "hello"`
publie un post test sur le profil et le supprime ensuite. Idem X et Reddit.

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
- Intégré dans EmailBot, SupportBot, ChatBot, ContentBot, OutboundBot
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
- ChatBot : intensité contrôle la longueur de réponse + temp + RAG depth

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
- Test des intégrations en 1 clic (LinkedIn / Mastodon / Reddit / Stripe / Gmail / Discord)
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

## 17.4 Chatbot site

- Bandeau au démarrage : « Vous discutez avec une IA. Vos messages sont stockés pour
  amélioration du service. »
- Respect du choix cookies (pas de tracking sans consentement)

## 17.5 Avis clients

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
| `kb-rag` | 6 | EmailBot, ChatBot, ContentBot, SupportBot |
| `stripe-ops` | 7 | FinanceBot |
| `chat-orchestrator` | 8 | ChatBot |
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
- `frontend-design` — chatbot widget (Partie 8) + Ops Dashboard (Partie 16)
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
- Latence p95 ChatBot < 5 s
- 0 breaker actif > 4 h
- 0 escalade Tier 2 sans réponse > 48 h

✅ **Done quand** : 7 jours consécutifs avec santé système verte, 0 incident humain.

---

# Annexe A — Dépendances entre parties

```
P0 → P1 → P2 → P3 → P4
                P3 → P5 → P6 → P14 → P15 → P16
                P3 → P7
                P3 → P8 (besoin P6)
                P3 → P11 → P9 → P10
                P3 → P12 (besoin P14, P15)
                P3 → P13 (besoin P5, P14, P15, P17)
P17 en parallèle de tout
P18 mise à jour à chaque création de skill
P19 démarre quand P4 existe
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
| 16-18 | P8 (ChatBot widget) | Sprint 1 |
| 19-20 | P11 (connecteurs sociaux) | Sprint 2 |
| 21-22 | P9 (ContentBot) | Sprint 2 |
| 23-24 | P10 (SEOBot) | Sprint 2 |
| 25 | **P16.B — Admin Panel Control (toggle, intensity)** | Sprint 2 |
| 26-27 | P12 (AdBot shadow mode) | Sprint 3 |
| 28-29 | P13 (OutboundBot) | Sprint 3 |
| 30 | **P16.C — Admin Panel Escalations queue** | Sprint 3 |
| 31 | **P16.D — Admin Panel KB editor + 2FA** | Sprint 4 |
| 32-33 | P19 (observabilité) | Continu |

Nota : dans la cadence du fondateur (10-12 sessions/jour), ces 30 jours de plan
peuvent se compresser à ~3-5 jours réels.

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
