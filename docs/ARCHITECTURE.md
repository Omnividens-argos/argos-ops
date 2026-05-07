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
   ContentBot P9          ChatBot P8            SupportBot P6
   SEOBot    P10          EmailBot in P5        FinanceBot P7
   AdBot     P12          DemoBot (phase 2)     AnalyticsBot
   OutboundBot P13        CallerBot (phase 2)
                              ▲
                              │
                    Agent-juge Tier 1 (P14)
                    Breakers (P15)
                    Admin Panel (P16)
```

Les agents sont des **slash commands Claude Code** lancés par cron. Ils lisent
et écrivent dans Postgres/Redis, appellent des APIs externes via les modules
`argos_ops.integrations.*`, et passent leurs sorties par l'agent-juge avant
envoi quand applicable.

---

## 2. Composants

| Composant | Rôle | Stack |
|-----------|------|-------|
| **Runtime de pensée** | Exécute les slash commands périodiquement | Claude Code Pro/Max via cron |
| **CRM + KB** | Stocke leads, interactions, tickets, agent_runs, kb_chunks | Postgres 16 (DB `argos_ops` sur cluster mutualisé SecHunter) + pgvector |
| **Cache / state** | Quotas, rate limits, idempotency keys | Redis 7 (DB index 3) |
| **Chat live** | Réponses temps réel sur `omnividens.fr` | Gemini 1.5 Flash (free tier) + RAG via pgvector |
| **Email inbound** | Lecture / draft / réponse `contact@omnividens.fr` | Gmail API + IMAP |
| **Email outbound** | Cold email volume modéré (≤ 50/jour) | Gmail API depuis domaine secondaire |
| **Sociaux** | Posting LinkedIn / Mastodon / Reddit | API natives via `argos_ops.integrations.*` |
| **Ads** | Pilotage Google / Meta / LinkedIn Ads | API natives, shadow mode tant que budget = 0 |
| **Analytics** | Pageviews + sources de trafic | Umami self-host (INFRA-02, à venir) |
| **Téléphonie** | (phase 2) | reporté |
| **Avatar démo** | (phase 2) | reporté |

---

## 3. Flux d'exécution typique d'un agent

Exemple : **EmailBot** (P5) lancé toutes les 15 min par cron.

```
cron */15 * * * *
   ↓
claude --print "/check-emails"           # slash command Claude Code
   ↓
agent_runtime.run_if_enabled('EmailBot', do_check_emails)
   ↓
Lecture agent_config        Postgres   ← admin panel peut désactiver
Vérification breakers       Postgres   ← P15 trip = skip
   ↓ (si OK)
Pull Gmail INBOX            Gmail API
   ↓
For each email:
   classify (skill email-classifier)
   lookup/create lead in CRM
   insert interaction direction='in'
   draft response (skill kb-rag → Gemini embedding + Claude)
   judge (skill claude-judge)           ← P14 supervision IA
     score ≥ 80 → send via Gmail
     50 ≤ score < 80 → draft + Discord notif
     score < 50 → kill, log
   insert interaction direction='out'
   ↓
log agent_runs              Postgres
   ↓
END
```

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

## 5. Stack technique figée

| Couche | Choix | Coût |
|--------|-------|------|
| Runtime de pensée | Claude Code Pro/Max via cron | déjà payé |
| Orchestration | cron Linux + scripts Python | 0 € |
| CRM | Postgres + pgvector | 0 € (DB existante) |
| Cache | Redis | 0 € (déjà en prod) |
| LLM chat live | Gemini 1.5 Flash free tier | 0 € |
| Embeddings KB | Gemini `embedding-001` | 0 € |
| Email | Gmail API | 0 € (≤ 500/jour) |
| Sociaux | LinkedIn / Mastodon / Reddit APIs | 0 € |
| Analytics | Umami self-host (INFRA-02) | 0 € |
| Total | | **~1 €/mois** (domaine secondaire outbound) |

---

## 6. Hébergement (D-001)

- Serveur : `204.168.171.71` (Ubuntu 24.04)
- Mutualisé avec SecHunter
- Caddy 2 (Alpine) reverse proxy : `ops.omnividens.fr` + `chat.omnividens.fr` (à
  brancher au moment opportun, P8 / P16)
- Postgres 16 : DB `argos_ops` séparée
- Redis 7 : DB index 3
- Cron : utilisateur `sechunter` (pas de nouvel utilisateur Linux)

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
