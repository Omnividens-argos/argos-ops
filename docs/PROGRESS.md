# Argos Ops — Progress

> Suivi de l'avancement des 19 parties du plan.
> Source : [`ARGOS_OPS_PLAN.md`](ARGOS_OPS_PLAN.md).
> À mettre à jour à chaque clôture de partie (règle « Clôture de partie » du
> [master prompt](MASTER_PROMPT.md)).

---

## Résumé d'avancement

- **Sessions terminées :** 13 / 18 (P8 cancelled, P0-P7 + P15 + P16.A + P10-MVP + P16.B done, **refonte UX P16** 2026-05-12, **P11-PREP-B Mastodon + P9-DRAFT + P14 ClaudeJudge** 2026-05-14)
- **Phase en cours :** Refonte UX du Admin Panel done (light/dark theme, catégorisation 6 catégories d'agents avec slots roadmap, status pills multi-états, Overview enrichi avec heatmap+sparklines, Runs groupé par jour, encart explicatif Breakers). Annexe D ajoutée au plan (7 agents proposés).
- **Dernière partie done :** Refonte UX P16 — invoque skills `ui-ux-pro-max` (palette light cohérente) + `frontend-design` (composants StatusPill, Sparkline, Heatmap, ThemeToggle). 7 nouveaux agents au plan (Annexe D).
- **Dernière décision structurante :** [D-019](DECISIONS.md#d-019--abandon-d%C3%A9finitif-du-chatbot-widget-site-p8-cancelled) — P8 ChatBot widget abandonnée définitivement.
- **Prochaine partie :** Sprint 2/4 reprise — Mastodon P11-PREP-B ✅ + P9-DRAFT ✅ + P14 ClaudeJudge ✅ done (2026-05-14). Reddit reporté (compte encore bugué), LinkedIn en attente d'approbation. Prochain candidat : **P11** dès que comptes débloqués, sinon **P12 AdBot shadow mode** (Sprint 3) ou **P19 maintenance** (health_check, observabilité).
- **3 Task Scheduler actifs** : `argos-ops-morning-digest` (0 8) + `argos-ops-email-bot` (*/15 8h-22h) + `argos-ops-finance-bot` (0 6) — Sprint 1 fermé côté infra cron
- **Task Scheduler créés (cron actifs)** : `argos-ops-morning-digest` (`0 8 * * *`) + `argos-ops-email-bot` (`*/15` 8h-22h Paris)
- **Repo GitHub :** [Omnividens-argos/argos-ops](https://github.com/Omnividens-argos/argos-ops) (privé)
- **Décision architecturale majeure (2026-05-08) :** [D-017](DECISIONS.md#d-017--argos-ops-100--local-first--claude-code-pro-max--embeddings-open-source-z%C3%A9ro-api-llm-tierce) — Argos Ops 100 % local-first via Claude Code Pro Max + embeddings open-source `paraphrase-multilingual-mpnet-base-v2` local. Aucune API LLM tierce. Trade-off : agents en pause quand l'ordi du fondateur est éteint.
- **Décision stack email (2026-05-08) :** [D-018](DECISIONS.md#d-018) — EmailBot via OVH Zimbra IMAP/SMTP `ssl0.ovh.net:993/465`. Boîte canonique `contact@omnividens.fr`.

---

## Parties

| # | Titre | Sprint | Statut | Date |
|---|-------|--------|--------|------|
| 0 | Vision et décisions préalables | — | ✅ done | 2026-05-07 |
| 1 | Préparation technique et choix d'hébergement | — | ✅ done (partiel) | 2026-05-07 |
| 2 | Bootstrap du dossier `argos-ops` | Sprint 0 | ✅ done | 2026-05-07 |
| 3 | Schéma CRM + Knowledge Base | Sprint 0 | ✅ done | 2026-05-08 |
| 4 | `/morning-digest` (premier slash command) | Sprint 0 | ✅ done | 2026-05-08 |
| 5 | EmailBot inbound (Zimbra IMAP/SMTP, D-018) | Sprint 1 | ✅ done (test live boucle IMAP→CRM→SMTP) | 2026-05-09 |
| 6 | SupportBot Tier 1 (RAG sur KB) | Sprint 1 | ✅ done (eval 10/10 PASS) | 2026-05-09 |
| 7 | FinanceBot (Stripe + relances) | Sprint 1 | ✅ done (test live OK, garde-fou DUNNING_ENABLED=false) | 2026-05-09 |
| ~~8~~ | ~~Chatbot widget site~~ — **🚫 cancelled** ([D-019](DECISIONS.md#d-019--abandon-d%C3%A9finitif-du-chatbot-widget-site-p8-cancelled)) | — | 2026-05-12 |
| 9 | ContentBot multi-canal | Sprint 2 | 🔄 P9-DRAFT done (skill `content-writer` + slash `/draft-content`, mode local-draft only — posting manuel jusqu'à P11) | 2026-05-14 |
| 10 | SEOBot stratégie + briefs | Sprint 2 | 🔄 P10-MVP done (brief writer, sans SERP — option A 2026-05-12) | 2026-05-12 |
| 11 | Connecteurs sociaux (LinkedIn / Mastodon / Reddit) | Sprint 2 | ⬜ pending | — |
| 12 | AdBot (pilotage Google/Meta/LinkedIn Ads) | Sprint 3 | ⬜ pending | — |
| 13 | OutboundBot (cold email volume modéré) | Sprint 3 | ⬜ pending | — |
| 14 | Agent-juge Tier 1 (supervision IA) | Sprint 4 | ✅ done (skill `claude-judge` + helper `argos_ops/judge.py` + 31 tests + 5 fixtures + stubs intégration 3 slash commands) | 2026-05-14 |
| 15 | Circuit breakers et kill switches | Sprint 4 | ✅ done | 2026-05-12 |
| 16 | Admin Control Panel (4 phases) | Sprints 1→4 | 🔄 P16.A + P16.B done (cockpit pilote en live, sans escalations queue) | 2026-05-12 |
| 17 | Conformité RGPD / AI Act / Bloctel | Continu | ⬜ pending | — |
| 18 | Inventaire des skills | Continu | ⬜ pending | — |
| 19 | Maintenance et observabilité | Continu | ⬜ pending | — |

Légende : ✅ done · 🔄 in progress · ⚠️ partial · 🚫 blocked · ⬜ pending

---

## Détail par partie

### P0 — Vision et décisions préalables ✅
**Done le 2026-05-07.** 5 décisions structurantes prises (D-001 à D-005, voir
`DECISIONS.md`). Pas de code livré. Décisions 4 (budget pub) et 5 (email
`contact@omnividens.fr`) repoussées à leur partie respective comme prévu.

### P1 — Préparation technique ✅ (partielle)
**Done le 2026-05-07.** 7 sous-tâches :
- ✅ P1.A Google AI Studio : clé Gemini validée (49 modèles)
- ✅ P1.B Discord : serveur + 4 webhooks + user ID
- ⏸️ P1.C Reddit : skippé (compte trop neuf, todo `P11-PREP`)
- ⏸️ P1.D X : skippé (free tier supprimé, remplacé par Mastodon — D-004)
- ✅ P1.E LinkedIn : 2 apps + Community Management API soumis (en attente 3-7j)
- ⏸️ P1.F Plausible : skippé (Umami à installer en INFRA-02)
- ✅ P1.G Validation finale

**Secrets stockés** dans `argos-ops/.env.local` (gitignored).

### P3 — Schéma CRM + Knowledge Base 🔄
**Bloc auto livré le 2026-05-07** (PR `feat/p3-crm-kb`). Reste : bloc manuel
(création DB serveur prod + rédaction KB authentique + seed final ≥50 chunks).

Livrables auto :
- Migration SQL `argos_ops/crm/migrations/0001_init.sql` (9 tables, pgvector,
  idempotente, alignée P3.1).
- Modèles SQLModel `argos_ops/crm/models.py` (768d Vector, types stricts).
- Module config `argos_ops/config.py` (pydantic-settings, SecretStr partout).
- Engine + session async `argos_ops/crm/db.py` (psycopg v3 async).
- Repository `argos_ops/crm/repository.py` (CRUD CRM + upsert KB idempotent par
  hash + recherche cosine pgvector).
- Chunker markdown `argos_ops/crm/kb_chunker.py` (split H2 + overlap).
- Script `scripts/seed_kb.py` (chunk → embed Gemini `gemini-embedding-001` →
  upsert, dry-run support).
- 19 tests unitaires (chunker, models, config) — pytest + ruff + mypy strict OK.

P3-M1 — DB locale (✅ done 2026-05-07, D-009) :
- Container Docker `argos-postgres-local` lancé (image `pgvector/pgvector:pg16`).
- DB `argos_ops`, user `argos_ops` (owner), volume persistant `argos_postgres_data`.
- Migration `0001_init.sql` appliquée → 9 tables + extension `vector` 0.8.2.
- `DATABASE_URL` mis à jour dans `.env.local`.
- Setup serveur reporté à P4/P5 (cf. D-009).

P3-M2 — Rédaction KB (✅ done 2026-05-08, mode interview) :
- ✅ `tone_of_voice.md` (2026-05-07, aligné 139 modules le 2026-05-08) —
  pitch canonique DAST-first, anti-FUD, table typographie, convention
  placeholders pour exclure les 4 cibles d'audit interne
- ✅ `ICP.md` (2026-05-07) — 3 personas (Marc/Sarah/Thomas), scoring BANT
  8 cases, déclencheurs OutboundBot, anti-ICP avec scripts verbatim,
  décisions différées (marque blanche, EN, DACH)
- ✅ `pricing.md` (2026-05-07, flags figés 2026-05-08 par D-010/011/012,
  aligné 139/41 le 2026-05-08) — 4 tiers (Free / Pro 39 € / Team 129 € /
  Pro Max 249 €) + Custom contact ≥5k€/mois, scans/jour vs par cible,
  -20 % annuel, 14 j refund, comparaison concurrence calibrée, glossaire
  canonique (Watch Pro Max only, Chaînes d'attaque Pro+, IA fallback auto
  = bascule entre BYOK configurés sans clé serveur Argos), add-on
  hors-quota Free-only confirmé
- ✅ `argos_features.md` (2026-05-08) — 1301 lignes, 78 KB, 7 sections :
  vue d'ensemble (139 modules / 41 Free), catalogue exhaustif des 139
  modules (6 sous-tableaux générés depuis registry SecHunter), 30 zooms
  emblématiques (Oracle/Finding/Différenciant), couche IA-corrélation
  (5 rôles + Strategist + Chaînes + Watch + Risk score + Compliance triple
  + BYOK fallback), antimatière 8 hors-scope, roadmap minimaliste, annexe
  machine-readable. Décisions : D-013 (Strategist framing) et D-014
  (compliance factuelle).
- ✅ `argos_modules.raw.json` (2026-05-08) — 48 KB, dump structuré des 139
  modules depuis registry SecHunter, croisé avec `_FREE_MODULES`. Annexe
  consultable par SupportBot en RAG hybride.
- ✅ `competitor_compare.md` (2026-05-08) — 586 lignes, 28 KB, 10 sections :
  positionnement canonique + matrice prix × périmètre, Argos vs Acunetix
  / Detectify / Burp Pro / Intruder / Pentera, hors comparable Snyk/SAST,
  anti-ICP (5 cas à éconduire), tableau récap vitamine cold call, règles
  anti-disparagement.
- ✅ `faq.md` (2026-05-08) — 772 lignes, 31 KB, ~50 Q&R en 10 sections
  (Pricing, Onboarding, Sécurité, Couverture, IA, Compliance, CI/CD, FP,
  Support, Divers). Décisions : D-015 (FP marking framing) et D-016
  (rétention purge en roadmap).

**4 décisions structurantes ajoutées le 2026-05-08** :
- D-010 / D-011 / D-012 (clôture flags pricing)
- D-013 / D-014 (Strategist framing + compliance factuelle)
- D-015 / D-016 (FP marking + rétention purge en roadmap)

**Tickets dev SecHunter à créer (suivi roadmap)** :
- `feat/strategist-prescriptive-routing` (~30 LOC) — fusion stratégie LLM
  + filtrage modules (cf. D-013)
- `feat/finding-mark-fp` (~150-200 LOC + UI) — bouton « Marquer FP »
  côté user (cf. D-015)
- `feat/findings-retention-cron` (~50 LOC) — purge auto par tier
  (cf. D-016)
- `fix/portscan-light-ghost-registry` — registrer `network.portscan_light`
  pour passer 41 → 42 modules Free (cf. note technique
  `argos_features.md` § 1.3)

P3-M3 — Seed + validation (✅ done 2026-05-08) :
- ✅ Refactor `seed_kb.py` : `fastembed` + `paraphrase-multilingual-mpnet-base-v2`
  local (D-017 — switch depuis Gemini suite au quota daily exhausted)
- ✅ Fix Windows `SelectorEventLoop` pour psycopg async
- ✅ Seed effectué : **93 chunks insérés** dans `kb_chunks` (cible ≥ 50 ✅)
- ✅ Test similarité « combien coûte Pro Max » → **top-1 et top-2 sont
  des chunks de `pricing.md`** (#5 dist=0.5485 « Annuel vs mensuel »,
  #0 dist=0.5698 « header Pricing canonique »). Critère P3 rempli ✅
- ✅ **D-017 — Argos Ops 100 % local-first** enregistrée + ARCHITECTURE.md
  + ARGOS_OPS_PLAN.md alignés. La couche données (Postgres + Redis +
  webhook receivers) reste sur serveur SecHunter (D-001 valide), la couche
  calcul (agents IA + cron + embeddings) migre sur l'ordi du fondateur.

**P3 entièrement done** — couche CRM + KB authentique + seed validé +
architecture alignée local-first. Sprint 0 complète à **2/4** (P0/P1/P2/P3
done, P4 prochain).

### P4 — `/morning-digest` ✅ done (test live 2026-05-08 23:03 CET)

**Code livré et tout vert** (ruff / format / mypy strict / **40 tests passed**) :

- `argos_ops/agents/base.py` — `BaseAgent` + `RunResult` + helper
  `run_agent()` qui enrobe l'exécution (breaker check → log start →
  appel `run()` → log end avec status final). Toutes les agents P5+
  hériteront de cette base
- `argos_ops/agents/digest_builder.py` — `DigestBuilder` agent + DTO
  `DigestKPIs` + `collect_kpis()` (lit leads/customers/tickets/breakers
  des dernières 24 h depuis Postgres) + `build_digest_embed()`
  (formatte en embed Discord avec couleur green/yellow/red selon état)
- `argos_ops/notifications/discord.py` — webhook push (embed + texte
  simple) avec couleurs canoniques + `httpx` async + raise sur HTTP ≥ 300
- `argos_ops/logging.py` — **filtre loguru anti-fuite secrets** (Discord
  webhooks, sk- API keys, AIza, gh_, xox_, whsec_, AKIA). Installé dès
  l'import du package (`argos_ops/__init__.py`). Réagi à un incident
  réel : le webhook Discord avait fuité dans les logs en cas d'erreur HTTP
  parce qu'`httpx.HTTPStatusError` inclut l'URL complète
- `scripts/run_digest.py` — entrée CLI invoquée par cron / Task Scheduler.
  Force `WindowsSelectorEventLoopPolicy` pour psycopg async sur Windows
- `.claude/commands/morning-digest.md` — slash command Claude Code
- `.claude/skills/digest-builder/SKILL.md` — skill formalisé avec
  procédure setup Task Scheduler Windows (UI + PowerShell scriptable)
- `tests/test_digest_builder.py` — 11 tests (couleurs + contenu embed +
  formatting leads breakdown)
- `tests/test_logging.py` — 9 tests sur le filtre anti-fuite

**Validation chaîne cron → Claude Code → action → log DB** :

- ✅ `agent_runs` table reçoit bien la ligne (id=1 testé en local avec
  `agent_name='DigestBuilder'`, `status='failed'` à cause du 503 webhook
  réseau le jour du test)
- ⚠️ Push Discord pas validé en live : webhook 503 + problème réseau /
  app Discord côté fondateur. Critère P3 du plan « digest valide sur
  Discord, ligne agent_runs avec status=success » **pas encore atteint**

**Test live passé le 2026-05-08 23:03 CET** : webhook Discord régénéré,
`uv run python scripts/run_digest.py` → `agent_runs id=2 status=success`,
embed digest visible sur Discord. Critère P3 du plan rempli ✅.

**Tâche cooldown restante (~5 min, non bloquante)** :

- ⚠️ Créer la **tâche Task Scheduler Windows** `argos-ops-morning-digest`
  selon la procédure dans
  [`.claude/skills/digest-builder/SKILL.md`](../.claude/skills/digest-builder/SKILL.md)
  (UI ou PowerShell scriptable), schedule `0 8 * * *` Paris

### P5 — EmailBot inbound (Zimbra IMAP/SMTP, D-018) ✅ done 2026-05-09

**Test live boucle complète passé le 2026-05-09** :

- ✅ Smoke test IMAP : login `ssl0.ovh.net:993` OK, 0 emails non lus
- ✅ Email envoyé manuellement à `contact@omnividens.fr` depuis
  `grogodumiot@gmail.com` (sujet `test`)
- ✅ Run `scripts/run_email_bot.py` → `agent_runs #3 status='success'`,
  `fetched=1 ingested=1 new_leads=1 new_companies=1`
- ✅ DB : `companies #1 domain=gmail.com source=email_inbound`,
  `leads #1 grogodumiot@gmail.com`, `interactions #1 channel=email
  direction=in subject=test`
- ✅ Embed Discord pushé sur webhook escalations (fallback car
  `DISCORD_WEBHOOK_INBOX` vide) — 2 embeds visibles côté fondateur
- ✅ Idempotence : 2e run = `fetched=0 ingested=0` (\\Seen positionné)
- ✅ `/check-emails` (humain-in-the-loop) : email classifié `autre`,
  draft validé, envoi SMTP `ssl0.ovh.net:465` OK, email reçu côté
  Gmail expéditeur, `interactions #2 direction=out
  judge_verdict=human_validated` loggé

**Code livré et tout vert** (ruff / format / mypy strict / **67 tests passed**) :

- `argos_ops/integrations/zimbra.py` — wrapper IMAP/SMTP OVH (D-018) :
  `EmailMessage` DTO, `fetch_unread()`, `mark_seen()`, `send_email()`,
  helpers `is_noreply()`, `extract_domain()`. `imap-tools` enrobé via
  `asyncio.to_thread`, `aiosmtplib` async natif
- `argos_ops/agents/email_bot.py` — `EmailBot(BaseAgent)` qui pull
  IMAP non-lus → persiste `companies/leads/interactions` → marque \Seen
  → push embed Discord. **Pas d'appel LLM** (D-017) — drafting via
  `/check-emails` humain-in-the-loop
- `scripts/run_email_bot.py` — entrée CLI cron (force WindowsSelectorEventLoopPolicy)
- `argos_ops/config.py` — variables `EMAIL_IMAP_HOST/PORT/USER/PASSWORD`,
  `EMAIL_SMTP_HOST/PORT`, `EMAIL_REPLY_NAME`, `DISCORD_WEBHOOK_INBOX`
- `.claude/skills/zimbra-ops/SKILL.md` — skill plomberie (lire/drafter/envoyer/marquer)
- `.claude/skills/email-classifier/SKILL.md` — skill inline Claude (8 catégories canoniques)
- `.claude/commands/run-email-bot.md` — slash command cron (cadence `*/15`)
- `.claude/commands/check-emails.md` — slash command interactif drafting humain-validé
- `tests/test_zimbra.py` (20 tests) + `tests/test_email_bot.py` (7 tests)
- `pyproject.toml` — ajout deps `imap-tools>=1.6` + `aiosmtplib>=3.0`
- `docs/ARGOS_OPS_PLAN.md` Partie 5 — révisée pour D-018 + D-017
  (pipeline split cron/automatique vs slash command/humain)

**Limites identifiées (à corriger en P5.1 si besoin)** :

- `interactions` ne stocke pas `message_id` → threading IMAP impossible
  pour les réponses (`In-Reply-To` non rempli). Pas bloquant pour P5
  (réponses arrivent quand même, juste pas threadées dans le client mail
  du destinataire). À corriger avec une migration ajoutant `message_id`,
  `in_reply_to`, `references` à la table `interactions`.

**Cooldowns DONE (2026-05-09)** :

- ✅ Task Scheduler `argos-ops-email-bot` créée (uv direct, cron `*/15` 8h-22h Paris)
- ✅ Task Scheduler `argos-ops-morning-digest` créée (uv direct, cron `0 8 * * *` Paris)
- ✅ PR `chore/email-signature` (#12) mergée — variante C brutaliste mono validée

### P6 — SupportBot Tier 1 (RAG sur KB) ✅ done 2026-05-09

**Eval 10/10 PASS** sur `scripts/eval_kb_rag.py` (5 questions IN-KB
répondent avec top doc correct, 5 questions hors-KB escaladent).

**Code livré et tout vert** (ruff + format + mypy strict + 12 nouveaux tests RAG) :

- `argos_ops/rag/embeddings.py` — singleton fastembed +
  `paraphrase-multilingual-mpnet-base-v2` (D-017), `embed_query()` +
  `embed_batch()` (réutilisé par `seed_kb.py`)
- `argos_ops/rag/search.py` — `search_kb()` (cosine top-K + filtre seuil
  `DEFAULT_DISTANCE_THRESHOLD=0.7` calibré sur eval),
  `RAGResult` (`is_empty` = signal escalade), `format_context_block()`,
  `build_support_prompt()` (prompt anti-hallucination strict)
- `scripts/eval_kb_rag.py` — eval golden 10 questions (IN-KB / OUT-KB)
- `scripts/seed_kb.py` — refactor pour utiliser `argos_ops.rag.embeddings`
- `.claude/skills/kb-rag/SKILL.md` — skill réutilisable (consommé par
  `/run-support-tier1`, `/check-emails`. _(ChatBot P8 initialement prévu
  comme consommateur de ce skill — annulé par D-019.)_
- `.claude/commands/run-support-tier1.md` — slash command interactive
- `.claude/commands/check-emails.md` — mise à jour pour invoquer `kb-rag`
  (étape 2.b du protocole)
- `tests/test_rag.py` — 12 tests unitaires (seuil, format, prompt, validation)

**Calibration eval** :
- IN-KB top distance : 0.473–0.561 (largement sous le seuil 0.7)
- OUT-KB top distance : 0.770+ ou 0 hits (au-dessus du seuil)
- Seuil 0.7 isole correctement les 2 régimes (calibré pour mpnet-base-v2)

### P15 — Circuit breakers et kill switches ✅ done 2026-05-12

**Code livré et tout vert** (ruff + format + mypy strict + **122 tests passed** = 106 P0-P7 + 16 nouveaux) :

- `argos_ops/breakers.py` — façade publique des breakers : `trip`, `reset`,
  `is_tripped`, `status`, `list_tripped`, `count_recent_failed`,
  `trip_with_notification` (idempotent, push Discord) + dataclass
  `BreakerStatus` + helper `in_minutes(n)` pour auto-reset par délai
- `argos_ops/crm/repository.py` — 3 nouvelles fonctions :
  `get_breaker`, `list_tripped_breakers` (auto-reset par `reset_after`
  pris en compte), `count_recent_failed_runs` (fenêtre temporelle)
- `argos_ops/agents/finance_bot.py` — `_maybe_trip_business_breakers` :
  trip `mrr_drop_critical` (severity=critical, MRR -10 % ou plus sur 7j)
  + `stripe_api_error_burst` (severity=critical, ≥3 runs failed sur 24h)
- `argos_ops/agents/email_bot.py` — `_maybe_trip_smtp_failures_burst`
  (severity=critical, ≥3 runs failed sur 24h)
- `scripts/reset_breaker.py` — CLI : `--list` affiche tripped, `<name>`
  reset
- `.claude/commands/reset-breaker.md` — slash command + checklist
  avant reset par breaker
- `tests/test_breakers.py` — 16 tests (idempotence, dataclass frozen,
  couleurs severity, no-webhook, swallow Discord error, etc.)

**Architecture** :

- Deux familles de breakers cohabitent. Les **kill switches globaux par
  agent** (`DigestBuilder`, `EmailBot`, `FinanceBot`) étaient déjà cablés
  via `BaseAgent.breaker_name` + `run_agent()` → bloquent l'exécution.
  Les **breakers métier** (`mrr_drop_critical`, etc.) trippés par la
  logique agent ne bloquent pas, juste alertent Discord + restent
  visibles jusqu'à reset manuel via `/reset-breaker`.
- `trip_with_notification` est **idempotent** : skip notif si déjà
  tripped (évite spam Discord à chaque cron). Reset requis pour
  re-alerter.

**Breakers du plan reportés à leur partie respective** :
`ad_spend_runaway` (P12 AdBot), `email_spam_complaints` (P13 OutboundBot),
`outbound_bounce_rate` (P13), `judge_disagreement` (P14 ClaudeJudge).
Cadre déjà en place — il suffira d'appeler `trip_with_notification` dans
ces agents.

**Hors scope (reporté à P19 maintenance)** : hook `PreToolUse` Claude
Code qui consulterait `is_breaker_tripped` avant chaque tool call.
Pas nécessaire au launch — le check est déjà dans `run_agent()`.

### P7 — FinanceBot (Stripe + relances) ✅ done 2026-05-09 (test live OK)

**Test live passé 2026-05-09** : clé restreinte Stripe live (`rk_live_...`) — Customers/Invoices/Subscriptions read-only — auth OK, premier run `agent_runs status='success'`, `mrr=0.00 active_subs=0/0` (early stage SecHunter, normal). Embed Discord posté sur canal `alerts`. Aucune relance envoyée (`DUNNING_ENABLED=false` garde-fou actif). Le bot se mettra automatiquement en route à la première sub Stripe.

**Task Scheduler créé** : `argos-ops-finance-bot` cron `0 6 * * *` Paris, invocation `uv run python scripts/run_finance_bot.py`.

**Sécurité** : la première clé `rk_live_...` a fuité dans le transcript (IDE remontait `.env.local` modifié dans system-reminders → leak). Clé révoquée, nouvelle clé générée, mémoire `feedback_secrets_via_ide_leak.md` enregistrée pour ne pas reproduire.

**Code livré et tout vert** (ruff + format + mypy strict + 18 nouveaux tests, **106 total**) :

- `argos_ops/integrations/stripe_client.py` — wrapper async (SDK Stripe
  sync enrobé via `asyncio.to_thread`). API : `fetch_active_subscriptions`,
  `fetch_open_invoices`, `compute_mrr_eur` (mensuel + annuel/12),
  `compute_arr_eur` (MRR×12), `classify_dunning_level` (J+3/J+7/J+15/none)
- `argos_ops/agents/finance_bot.py` — `FinanceBot(BaseAgent)` complet :
  pull subs → upsert `companies` (stripe_customer_id, subscription_status,
  mrr_eur, stripe_synced_at) → calcul MRR + ARR + delta vs S-1 → dunning
  idempotent (skip si déjà envoyé via `interactions.judge_verdict`) →
  notif Discord embed (canal `alerts`, fallback `ops_logs`)
- 3 templates de relance dégradés (J+3 amical / J+7 ferme / J+15 escalade)
- `scripts/run_finance_bot.py` — entrée CLI cron
- `argos_ops/crm/migrations/0002_p7_stripe.sql` — applique sur DB locale,
  ajoute 4 colonnes Stripe sur `companies`
- `argos_ops/crm/models.py` — `Company` étendue (4 champs Stripe)
- `argos_ops/config.py` — `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`,
  `FINANCEBOT_DUNNING_ENABLED` (default false)
- `.claude/skills/stripe-ops/SKILL.md` — skill réutilisable
- `.claude/commands/daily-finance-sync.md` — slash command cron
- `tests/test_finance_bot.py` — 18 tests (calcul MRR + dunning levels +
  templates rendus + couleurs embed)

**Garde-fou explicite** : `FINANCEBOT_DUNNING_ENABLED=false` par défaut.
Quand désactivé, FinanceBot fait tout (sync + MRR + Discord) sauf l'envoi
outbound — il logge juste « [DUNNING_DISABLED] J+N aurait été envoyé pour
{invoice} ». À activer après audit du premier run live.

**Tâches restantes (~15 min côté fondateur)** :

1. Coller `STRIPE_SECRET_KEY=sk_live_...` dans `.env.local` (compte
   Stripe partagé avec SecHunter — clé déjà existante côté SecHunter)
2. Premier run live `uv run python scripts/run_finance_bot.py` avec
   `DUNNING_ENABLED=false` → audit du MRR + companies synchronisées
3. Vérifier l'embed Discord sur le canal alerts/ops_logs
4. Si tout OK → passer `FINANCEBOT_DUNNING_ENABLED=true` puis lancer un
   2e run pour valider 1 ou 2 envois de relance
5. Créer la Task Scheduler `argos-ops-finance-bot` cron `0 6 * * *` Paris
   (PowerShell scriptable dans `.claude/skills/stripe-ops/SKILL.md`)

### P9-DRAFT — ContentBot mode local-draft only 🔄 done 2026-05-14

**Pivot Sprint 2** : P11 (connecteurs sociaux) bloqué (compte Reddit
encore bugué + LinkedIn en attente d'approbation Community Management API).
Pour produire de la valeur côté comms en parallèle, on livre la couche
draft du ContentBot sans toucher au posting automatique. Pattern aligné
sur P10-MVP (skill markdown + slash command, pas d'agent Python à ce stade).

**Livrables (aucun code Python — skill éditorial pur)** :

- `.claude/skills/content-writer/SKILL.md` — skill éditorial. 4 canaux
  supportés (LinkedIn 1300-2000 chars / Mastodon 450-500 / Reddit r/netsec
  800-2000 mots / X ≤ 280), contraintes par canal, garde-fous (zéro stat
  inventée, zéro FUD, zéro buzzword corporate, zéro cross-posting
  identique, règle 9:1 Reddit stricte). Consomme `kb-rag` (P6) +
  `tone_of_voice.md` + `ICP.md` systématiquement.
- `.claude/commands/draft-content.md` — slash command humain-in-the-loop.
  Drafting mode interview court (angle → hook → corps → CTA → hashtags).
  Refuse fermement les anti-patterns avant écriture fichier.
- `data/content/drafts/` — queue locale de drafts (créée vide).
  `data/content/README.md` documente workflow actuel (manuel) vs futur
  (post-P11 — ContentBot lit cette même queue et poste auto).

**Frontmatter draft canonique** (parseable par futur ContentBot agent
quand P11 sera live) :

```yaml
---
channel: linkedin | mastodon | reddit | x
status: draft | validated | posted | rejected
date_created: YYYY-MM-DD
posted_at: null | YYYY-MM-DDTHH:MM
topic: "<topic court>"
angle: "<angle retenu>"
character_count: <int>
word_count: <int>     # Reddit longform
kb_sources: ["pricing.md§Pro Max", ...]
cta: "<lien ou null>"
url_posted: null      # rempli manuellement après posting
---
```

**Workflow boucle hebdo (jusqu'à P11)** :

1. `/draft-content <channel> <topic>` 2-5×/semaine
2. Skill produit draft validé dans `data/content/drafts/`
3. Fondateur copie-colle dans le canal et publie
4. Fondateur édite frontmatter : `status: posted` + `posted_at` + `url_posted`

**Transition P9 full (post-P11)** : ContentBot agent Python lira cette
queue, filtrera `status: validated`, soumettra à `ClaudeJudge` (P14),
postera via `argos_ops/integrations/{linkedin,mastodon,reddit}.py` puis
récupérera engagement J+1 dans `interactions.judge_score`. Le format
des drafts ne bougera pas — pas de migration data nécessaire.

**Hors scope P9-DRAFT** (volontaire — couvert par P9 full) :
- Table `editorial_calendar` (P9 § 9.1) — pas nécessaire tant que le
  fondateur drive le rythme manuellement
- Skill `content-scheduler` (heure optimale par canal) — utile seulement
  quand le posting devient automatique
- Connecteurs sociaux Python (P11)
- Agent-juge (P14)

**Test plan (à dérouler avant clôture finale P9-DRAFT)** :
- [ ] `/draft-content linkedin "faux positifs DAST"` → draft généré,
      character_count 1300-2000, kb_sources non vide
- [ ] `/draft-content mastodon "<topic>"` → 450-500 chars, pas d'emoji
      marketing, lien à la fin
- [ ] `/draft-content reddit "<topic>"` sans validation 9:1 → refus +
      proposition alternative
- [ ] Garde-fou stat inventée → refus

### P14 — Agent-juge Tier 1 (claude-judge) ✅ done 2026-05-14

**Pivot D-017** : sous le régime local-first, le « juge » n'est pas un
appel API LLM autonome — c'est Claude Code lui-même, invoqué via le
skill `claude-judge` depuis un slash command de drafting AVANT validation
humaine. Pas de coût marginal (compris dans Pro Max abonnement fondateur).

**Code livré et tout vert** (ruff + format + mypy strict + **186 tests
passed** = 155 P0-P15 + 31 nouveaux) :

- [`argos_ops/judge.py`](../argos_ops/judge.py) — plomberie Python :
  - `JudgeReport` dataclass frozen avec validation des scores [0, 100]
  - `parse_judge_json(text)` robuste : accepte JSON brut, fenced
    ```json ... ```, texte parasite around, propage les erreurs
    de validation des scores
  - `apply_thresholds(report)` — règles déterministes ESCALATION_RULES.md
    (auto_send si global ≥ 80 ∧ factual ≥ 70 ∧ legal ≥ 90 ; killed si
    factual < 50 ∨ legal < 50 ∨ global < 50 ; sinon queued)
  - `save_judge_verdict(...)` async — persiste l'interaction avec
    `judge_score = report.global_score` + `judge_verdict =
    apply_thresholds(report)`. Python tranche, jamais le LLM directement
- [`.claude/skills/claude-judge/SKILL.md`](../.claude/skills/claude-judge/SKILL.md)
  — grille de scoring 3 axes documentée :
  - **factual** : chaque claim soutenu par les chunks RAG ? Fail = stat
    inventée, prix faux, feature inventée, citation fictive
  - **tone** : alignement `tone_of_voice.md` (anti-buzzword, anti-FUD,
    vocabulaire registre maison)
  - **legal** : RGPD / AI Act / Bloctel / anti-disparagement
    (`competitor_compare.md` § 10) / PII tiers / secret leak
  - JSON output strict, fenced markdown recommandé, **pas** de champ
    `verdict` côté LLM
- [`data/judge/`](../data/judge/) — fixtures golden starter :
  - `001_email_factuel_clean.yaml` — auto_send (baseline)
  - `002_email_hallucination_prix.yaml` — killed (factual < 50)
  - `003_linkedin_buzzword_innovant.yaml` — queued (tone)
  - `004_outbound_pas_optout.yaml` — killed (legal < 50)
  - `005_seo_brief_disparage_burp.yaml` — queued (legal modéré)
  - Target P14.1 : étendre vers 50 fixtures
- [`tests/test_judge.py`](../tests/test_judge.py) — 31 tests :
  validation `JudgeReport`, parsing robuste (4 formats), règles
  thresholds (incluant table paramétrée de boundary cases)
- **Stubs intégration** dans :
  - [`.claude/commands/check-emails.md`](../.claude/commands/check-emails.md)
    — invoque claude-judge entre RAG et soumission au fondateur, persiste
    le verdict via `save_judge_verdict`
  - [`.claude/commands/draft-content.md`](../.claude/commands/draft-content.md)
    — refuse d'écrire si verdict=killed, marque `status: queued` si
    queued, intègre `judge_score / judge_verdict / judge_rationale` au
    frontmatter
  - [`.claude/commands/generate-seo-brief.md`](../.claude/commands/generate-seo-brief.md)
    — même pattern, status `ready` si auto_send (consommable direct par
    ContentBot futur P9 full)

**Schéma DB** : `interactions.judge_score` + `interactions.judge_verdict`
existaient déjà depuis P3 (migration `0001_init.sql`). Aucune migration
nécessaire.

**Hors scope P14** (reporté à P14.1 quand on observera des FP/FN en prod) :

- `scripts/eval_judge.py` — boucle sur toutes les fixtures, calcule taux
  de désaccord. Bloqué tant que Claude Code n'expose pas un mode
  scriptable headless pour invoquer un skill — pour l'instant éval manuelle
- Étendre vers 50 fixtures (cf. backlog dans `data/judge/README.md`)
- Breaker `judge_disagreement` (cadre P15 déjà en place — il suffira
  d'appeler `trip_with_notification` quand > 20 % des verdicts de la
  journée sont `queued`)

### P2 — Bootstrap du dossier `argos-ops` ✅
**Done le 2026-05-07.** Repo privé GitHub créé et premier push effectué.
Livrables :
- Arborescence projet complète (16 dossiers, 24+ fichiers)
- `pyproject.toml` validé via `uv sync` (97 packages résolus, 15 deps importables)
- 6 docs (DECISIONS, PROGRESS, ARCHITECTURE, AGENTS_PLAYBOOK, ESCALATION_RULES, COMPLIANCE)
- 7 décisions structurantes documentées (D-001 à D-007)
- `CLAUDE.md` projet + `README.md` + `.env.example` + `.gitignore`
- `.env.local` migré depuis `../the good guy/.argos-ops-secrets.local`
- 3 commits sur `main` (bootstrap + fix google-genai + clôture)
- Repo GitHub privé : [Omnividens-argos/argos-ops](https://github.com/Omnividens-argos/argos-ops)

**Note** : push direct sur main accepté pour le bootstrap (le repo n'existait pas
avant). Branch protection activée à la fin de P2 → dès P3, tout passe par
branche/PR/merge comme stipulé dans `CLAUDE.md`.

---

## Sessions transverses (non numérotées)

| ID | Titre | Statut | Note |
|----|-------|--------|------|
| INFRA-01 | (réservé pour future install lourde si besoin) | — | — |
| INFRA-02 | Install Umami self-host | ⬜ pending | Avant P10 ou P12 |
| P11-PREP-A | Recréer Reddit App (compte vieilli) | ⏸️ reporté (compte encore bugué — 2026-05-14) | Avant P11 |
| P11-PREP-B | Créer compte Mastodon infosec.exchange + token | ✅ done (compte `@argos_omnividens@infosec.exchange`, token validé via `scripts/smoke_mastodon.py` 2026-05-14) | TODO bio + bot flag |
| P17-PREP | Page `/legal/privacy` + `/legal/ai-disclosure` sur omnividens.fr | ⚠️ rédaction faite (data/legal/), intégration frontend SecHunter à faire par user | rédaction 2026-05-08 |
| P1.E-FOLLOWUP | Vérifier approbation Community Management API LinkedIn | ⬜ pending | 3-7j après 2026-05-07 |

---

## Métriques globales (à remplir à mesure)

- **Skills `argos-ops` créés :** 1 / 14 prévus (`digest-builder` en P4, voir P18)
- **Slash commands installés :** 1 (`/morning-digest` — partial, attend test live)
- **Agents en production :** 0 / 12 (DigestBuilder code livré, prod après finalisation P4)
- **Coût mensuel cumulé Argos Ops :** 0 € (cible : ≤ 1 €/mois en croisière)
