# Argos Ops — Architecture

> Vue d'ensemble technique. Pour le **plan stratégique** voir
> [`ARGOS_OPS_PLAN.md`](ARGOS_OPS_PLAN.md). Pour les **décisions** voir
> [`DECISIONS.md`](DECISIONS.md).

---

## 1. Vue à 50 000 ft

```
┌─────────────────────────────────────────────────────────────────┐
│  CRM + Knowledge Base central (Postgres + pgvector + Redis)     │
└─────────────────────────────────────────────────────────────────┘
                              ▲
        ┌─────────────────────┼─────────────────────┐
   ACQUISITION            CONVERSION            RÉTENTION
   (top funnel)           (mid funnel)          (bottom funnel)
   ContentBot P9          EmailBot in P5        SupportBot P6
   SEOBot    P10          DemoBot (phase 2)     FinanceBot P7
   AdBot     P12          CallerBot (phase 2)   AnalyticsBot
   OutboundBot P13
                              ▲
                              │
                    Agent-juge Tier 1 (P14)
                    Breakers (P15)
                    Admin Panel (P16)
```

> _Note : ChatBot widget P8 retiré du périmètre 2026-05-12 — cf.
> [D-019](DECISIONS.md#d-019--abandon-d%C3%A9finitif-du-chatbot-widget-site-p8-cancelled).
> Le canal entrant prospects/visiteurs reste l'email
> (`contact@omnividens.fr` via EmailBot P5 + SupportBot P6)._

Les agents sont des **slash commands Claude Code** lancés par cron **sur
l'ordi du fondateur** (cf. [`DECISIONS.md` D-017](DECISIONS.md#d-017--argos-ops-100--local-first--claude-code-pro-max--embeddings-open-source-z%C3%A9ro-api-llm-tierce)).
Ils lisent et écrivent dans Postgres/Redis sur le serveur SecHunter, appellent
des APIs externes via les modules `argos_ops.integrations.*`, et passent leurs
sorties par l'agent-juge avant envoi quand applicable. **Aucun appel LLM
sortant** : tout passe par l'abonnement Claude Code Pro Max du fondateur.

---

## 2. Composants

| Composant | Rôle | Stack | Hébergement |
|-----------|------|-------|------|
| **Runtime de pensée** | Exécute les slash commands Claude Code périodiquement | Claude Code Pro/Max | **ordi fondateur** (D-017) |
| **CRM + KB** | Stocke leads, interactions, tickets, agent_runs, kb_chunks | Postgres 16 (DB `argos_ops`) + pgvector | serveur SecHunter (D-001) |
| **Cache / state / queue** | Quotas, rate limits, idempotency keys | Redis 7 (DB index 3) | serveur SecHunter (D-001) |
| **Webhook receivers** | Endpoints HTTP futurs (Stripe push, etc.) | FastAPI + Caddy reverse proxy | serveur SecHunter (24/7) |
| **Embeddings KB** | Génère les vecteurs 768d des chunks markdown pour pgvector | `fastembed` + `paraphrase-multilingual-mpnet-base-v2` (CPU, ONNX, ~280 MB poids) | **ordi fondateur** (D-017) |
| **Email inbound** | Lecture / draft / réponse `contact@omnividens.fr` | IMAP/SMTP OVH Zimbra (D-018) | runtime ordi fondateur |
| **Email outbound** | Cold email volume modéré (≤ 50/jour) | Gmail API depuis domaine secondaire | runtime ordi fondateur |
| **Sociaux** | Posting LinkedIn / Mastodon (D-022 retire Reddit) | API natives via `argos_ops.integrations.*` | runtime ordi fondateur |
| **Ads** | Pilotage Google / Meta / LinkedIn Ads | API natives, shadow mode tant que budget = 0 | runtime ordi fondateur |
| **Analytics** | Pageviews + sources de trafic | Umami self-host (INFRA-02, à venir) | serveur SecHunter |
| **Téléphonie** | (phase 2) | reporté | — |
| **Avatar démo** | (phase 2) | reporté | — |

---

## 3. Flux d'exécution typique d'un agent

Exemple : **EmailBot** (P5) lancé toutes les 15 min par cron **sur l'ordi
du fondateur** (cf. D-017).

```
[ORDI fondateur]
cron */15 * * * *  (Task Scheduler Windows ou cron WSL2)
   ↓
claude --print "/check-emails"           # slash command Claude Code
                                         # consomme abonnement Pro Max
   ↓
agent_runtime.run_if_enabled('EmailBot', do_check_emails)
   ↓
[Postgres distant — serveur SecHunter via psycopg async]
Lecture agent_config        ← admin panel peut désactiver
Vérification breakers       ← P15 trip = skip
   ↓ (si OK)
[ORDI fondateur]
Pull Gmail INBOX            Gmail API (oauth user)
   ↓
For each email:
   classify (skill email-classifier — Claude inline)
   embed local (fastembed e5-base, CPU)  ← ~50 ms/chunk
   lookup/create lead       INSERT/SELECT Postgres distant
   insert interaction direction='in'
   draft response (skill kb-rag → similarity search pgvector + Claude)
   judge (skill claude-judge)            ← P14 supervision IA, Claude inline
     score ≥ 80 → send via Gmail
     50 ≤ score < 80 → draft + Discord notif (webhook)
     score < 50 → kill, log
   insert interaction direction='out'
   ↓
log agent_runs              Postgres distant
   ↓
END
```

> _Flux webhook 24/7 chat widget retiré par
> [D-019](DECISIONS.md#d-019--abandon-d%C3%A9finitif-du-chatbot-widget-site-p8-cancelled).
> Les futurs webhooks (Stripe push, etc.) reprendront un pattern pull-based
> Redis similaire si besoin se présente._

---

## 4. Système d'escalade Tier 0-4

| Tier | Acteur | Volume cible |
|------|--------|--------------|
| 0 | Agent répond directement | 90 % |
| 1 | Agent-juge IA valide la réponse | 8 % |
| 2 | File asynchrone, fondateur lit 2×/jour, SLA 24 h | 1.5 % |
| 3 | VA externe (~5 €/h) si volume dépasse | 0.4 % |
| 4 | Fondateur en synchrone, vrais P0 | 0.1 % |

Voir [`ESCALATION_RULES.md`](ESCALATION_RULES.md) pour les règles précises.

---

## 5. Stack technique figée (v2 — D-017)

| Couche | Choix | Coût | Hébergement |
|--------|-------|------|------|
| Runtime de pensée | Claude Code Pro/Max via cron / Task Scheduler | **déjà payé** (abonnement fondateur) | ordi fondateur |
| Orchestration | cron / Windows Task Scheduler + scripts Python | 0 € | ordi fondateur |
| CRM | Postgres + pgvector | 0 € (DB existante) | serveur SecHunter |
| Cache + queue | Redis (cache + idempotency keys agents) | 0 € (déjà en prod) | serveur SecHunter |
| **LLM agents (tous)** | **Claude Code Pro Max via slash commands** | **0 € (forfait Pro Max)** | runtime ordi |
| **Embeddings KB** | **`fastembed` + `multilingual-e5-base` (CPU local)** | **0 € forever** | ordi fondateur |
| Email | Gmail API | 0 € (≤ 500/jour) | runtime ordi |
| Sociaux | LinkedIn / Mastodon APIs (D-022 retire Reddit) | 0 € | runtime ordi |
| Analytics | Umami self-host (INFRA-02) | 0 € | serveur SecHunter |
| Webhook receivers | FastAPI + Caddy reverse proxy | 0 € | serveur SecHunter |
| Total | | **~1 €/mois** (domaine secondaire outbound) | — |

**Aucune API LLM tierce** (Gemini, OpenAI, Voyage, Anthropic API) n'est
utilisée par Argos Ops. Tout passe par l'abonnement Claude Code Pro Max
du fondateur (cf. [D-017](DECISIONS.md#d-017--argos-ops-100--local-first--claude-code-pro-max--embeddings-open-source-z%C3%A9ro-api-llm-tierce)).

> **À ne pas confondre** : le **scanner Argos / SecHunter** (le produit
> qu'on vend aux clients) garde son architecture **BYOK multi-provider**
> côté client (cf. [D-011](DECISIONS.md#d-011--ia-fallback-auto-pro-max--byok-seul-pas-de-cl%C3%A9-serveur-argos)).
> D-017 ne s'applique qu'à **Argos Ops** (la flotte interne).

---

## 6. Hébergement (D-001 partiellement révisé par D-017)

**Couche données + endpoints HTTP — serveur SecHunter** (`204.168.171.71`,
Ubuntu 24.04, mutualisé) :

- Postgres 16 : DB `argos_ops` (D-001)
- Redis 7 : DB index 3 (D-001)
- Caddy 2 reverse proxy : `ops.omnividens.fr` (P16). _(`chat.omnividens.fr`
  retiré par [D-019](DECISIONS.md#d-019--abandon-d%C3%A9finitif-du-chatbot-widget-site-p8-cancelled).)_
- FastAPI webhook receivers : pour de futurs événements 24/7 (Stripe push,
  etc.) si besoin se présente

**Couche calcul agents IA — ordi fondateur** (D-017) :

- Cron / Windows Task Scheduler invoque Claude Code (slash commands)
- Modèle d'embedding `multilingual-e5-base` (CPU, ONNX, ~280 MB)
- Connexion Postgres / Redis distants vers le serveur SecHunter via
  `psycopg` async / `redis-py` async (TLS)
- `.env.local` (gitignored) contient les secrets API tiers (Gmail OAuth,
  LinkedIn, Mastodon, Stripe, Discord webhook)

**Trade-off accepté** (D-017) : agents en pause quand l'ordi est éteint.
Webhooks 24/7 absorbés par la queue Redis, traités au prochain cycle de
l'ordi.

---

## 7. Secrets et configuration

- `.env.local` (gitignored) — secrets en local pendant le développement
- `.env` (sur le serveur prod, gitignored) — secrets en production
- `.env.example` (committed) — liste complète des variables sans valeur
- Aucun secret dans le code, aucun secret dans les logs

---

## 8. Pour aller plus loin

- [`AGENTS_PLAYBOOK.md`](AGENTS_PLAYBOOK.md) — détail des 12 agents
- [`ESCALATION_RULES.md`](ESCALATION_RULES.md) — règles Tier 0-4
- [`COMPLIANCE.md`](COMPLIANCE.md) — RGPD / AI Act / Bloctel
- [`DECISIONS.md`](DECISIONS.md) — journal des décisions structurantes
- [`PROGRESS.md`](PROGRESS.md) — état d'avancement
