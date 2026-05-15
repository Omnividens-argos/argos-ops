# Argos Ops — Progress

> Suivi de l'avancement des 21 parties du plan.
> Source : [`ARGOS_OPS_PLAN.md`](ARGOS_OPS_PLAN.md).
> À mettre à jour à chaque clôture de partie (règle « Clôture de partie » du
> [master prompt](MASTER_PROMPT.md)).

---

## Résumé d'avancement

- **Sessions terminées :** 17 / 18 (P8 cancelled, P0-P7 + P15 + P16.A + P10-MVP + P16.B done, **refonte UX P16** 2026-05-12, **P11-PREP-B Mastodon + P9-DRAFT + P14 ClaudeJudge + P19.0 health_check + P12 shadow + P17 compliance + P18 skills inventory** 2026-05-14)
- **Phase en cours :** Refonte UX du Admin Panel done (light/dark theme, catégorisation 6 catégories d'agents avec slots roadmap, status pills multi-états, Overview enrichi avec heatmap+sparklines, Runs groupé par jour, encart explicatif Breakers). Annexe D ajoutée au plan (7 agents proposés).
- **Dernière partie done :** Refonte UX P16 — invoque skills `ui-ux-pro-max` (palette light cohérente) + `frontend-design` (composants StatusPill, Sparkline, Heatmap, ThemeToggle). 7 nouveaux agents au plan (Annexe D).
- **Dernière décision structurante :** [D-021](DECISIONS.md#d-021--param%C3%A9trage-inter-agents--capabilities-pull-based-default-allow-pour-read--deny-pour-write-back) — Paramétrage inter-agents pull-based (P21) ajouté au plan (2026-05-15), complémentaire de [D-020](DECISIONS.md#d-020--argos-memory--m%C3%A9moire-vivante-partag%C3%A9e-multi-agents-architecture-5-couches) (Argos Memory P20).
- **Prochaine partie :** **P20 Argos Memory** puis **P21 Capabilities** (les deux nouvelles, prioritaires sur P11. P20 = bus de communication ; P21 = règles de combinaison. Cf. D-020 + D-021). Reste aussi **P11** (LinkedIn seulement maintenant — Reddit retiré [D-022](DECISIONS.md#d-022--retrait-d%C3%A9finitif-de-reddit-du-p%C3%A9rim%C3%A8tre-argos-ops), Mastodon déjà OK), **P13 OutboundBot** (besoin domaine secondaire ~10 €/an) et le **live mode** des agents shadow (P9 full, P12.B, P10 full SERP).
- **3 Task Scheduler actifs** : `argos-ops-morning-digest` (0 8) + `argos-ops-email-bot` (*/15 8h-22h) + `argos-ops-finance-bot` (0 6) — Sprint 1 fermé côté infra cron
- **Task Scheduler à enregistrer** : `argos-ops-health-check` (5h45 daily) — script PowerShell idempotent livré dans [`scripts/setup_health_check_task.ps1`](../scripts/setup_health_check_task.ps1). À lancer en PS admin une fois côté fondateur (`.\scripts\setup_health_check_task.ps1`).
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
| 11 | Connecteurs sociaux (LinkedIn / Mastodon) | Sprint 2 | ⬜ pending — Reddit retiré [D-022](DECISIONS.md#d-022--retrait-d%C3%A9finitif-de-reddit-du-p%C3%A9rim%C3%A8tre-argos-ops) 2026-05-15 | — |
| 12 | AdBot (pilotage Google/Meta/LinkedIn Ads) | Sprint 3 | 🔄 P12 shadow done (skills `ads-creative-writer` + `ads-optimizer` + slashs `/draft-ad` + `/analyze-ads` + data/ads/ tree, mode shadow only — pas d'API tant que budget pub pas branché) | 2026-05-14 |
| 13 | OutboundBot (cold email volume modéré) | Sprint 3 | 🔄 P13.A shadow done (module `argos_ops/outbound/` + agent `OutboundBot` + slashs `/run-outbound-bot` + `/draft-outbound` + breaker `outbound_volume_exceeded` + 29 tests. Mode shadow strict — aucun envoi tant que domaine secondaire + `OUTBOUND_LIVE_MODE=true`) | 2026-05-15 |
| 14 | Agent-juge Tier 1 (supervision IA) | Sprint 4 | ✅ done (skill `claude-judge` + helper `argos_ops/judge.py` + 31 tests + 5 fixtures + stubs intégration 3 slash commands) | 2026-05-14 |
| 15 | Circuit breakers et kill switches | Sprint 4 | ✅ done | 2026-05-12 |
| 16 | Admin Control Panel (4 phases) | Sprints 1→4 | 🔄 P16.A + P16.B done (cockpit pilote en live, sans escalations queue) | 2026-05-12 |
| 17 | Conformité RGPD / AI Act / Bloctel | Continu | ✅ done côté Argos Ops (privacy + ai-disclosure rédigés + `compliance.py` AI Act § 5.2 + check-emails wired + 22 tests) — intégration frontend SecHunter reste côté user | 2026-05-14 |
| 18 | Inventaire des skills | Continu | ✅ done (3 skills ajoutés : `content-scheduler` + `lead-enricher` + `outbound-personalizer`. Inventaire complet sauf `serp-analyzer` reporté en P10.1 / option B) | 2026-05-14 |
| 19 | Maintenance et observabilité | Continu | 🔄 P19.0 done — `argos_ops/health.py` + `scripts/health_check.py` (DB / KB / agent freshness / breakers / queued escalations) + 23 tests. Hooks Claude Code reportés (déjà couverts par `run_agent()` wrapper P15) | 2026-05-14 |
| 20 | Argos Memory (5 couches : raw / SQL / semantic / curator / auditor) | Sprint 2+ | ⬜ pending — spec ajoutée 2026-05-15, [D-020](DECISIONS.md#d-020--argos-memory--m%C3%A9moire-vivante-partag%C3%A9e-multi-agents-architecture-5-couches). 4 sous-parties P20.A → P20.D | — |
| 21 | Paramétrage inter-agents (capabilities pull-based, table + Admin Panel matrice + write-back) | Sprint 2+ (après P20.A) | ⬜ pending — spec ajoutée 2026-05-15, [D-021](DECISIONS.md#d-021--param%C3%A9trage-inter-agents--capabilities-pull-based-default-allow-pour-read--deny-pour-write-back). 3 sous-parties P21.A → P21.C | — |

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
- 🚫 ~~P1.C Reddit~~ : skippé en P1 (compte trop neuf, D-005). Reddit **définitivement retiré** du périmètre Argos Ops par [D-022](DECISIONS.md#d-022--retrait-d%C3%A9finitif-de-reddit-du-p%C3%A9rim%C3%A8tre-argos-ops) 2026-05-15
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

**Pivot Sprint 2** : P11 (connecteurs sociaux) bloqué (LinkedIn en
attente d'approbation Community Management API ; Mastodon OK ; Reddit
retiré du périmètre par [D-022](DECISIONS.md#d-022--retrait-d%C3%A9finitif-de-reddit-du-p%C3%A9rim%C3%A8tre-argos-ops) 2026-05-15).
Pour produire de la valeur côté comms en parallèle, on livre la couche
draft du ContentBot sans toucher au posting automatique. Pattern aligné
sur P10-MVP (skill markdown + slash command, pas d'agent Python à ce stade).

**Livrables (aucun code Python — skill éditorial pur)** :

- `.claude/skills/content-writer/SKILL.md` — skill éditorial. 2 canaux
  supportés (LinkedIn 1300-2000 chars / Mastodon 450-500 chars) après
  [D-022](DECISIONS.md#d-022--retrait-d%C3%A9finitif-de-reddit-du-p%C3%A9rim%C3%A8tre-argos-ops)
  qui retire Reddit. X reste mentionné « bas priorité » (D-004 free tier
  supprimé). Garde-fous (zéro stat inventée, zéro FUD, zéro buzzword
  corporate, zéro cross-posting identique). Consomme `kb-rag` (P6) +
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
channel: linkedin | mastodon | x
status: draft | validated | posted | rejected
date_created: YYYY-MM-DD
posted_at: null | YYYY-MM-DDTHH:MM
topic: "<topic court>"
angle: "<angle retenu>"
character_count: <int>
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
postera via `argos_ops/integrations/{linkedin,mastodon}.py` puis
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
- [ ] Garde-fou stat inventée → refus

### P18 — Inventaire des skills ✅ done 2026-05-14

Tous les skills planifiés au plan §18 sont livrés (sauf `serp-analyzer`
reporté en P10.1 / option B 2026-05-12). Les agents Python correspondants
restent à câbler avec leurs connecteurs API quand les credentials /
budgets associés seront disponibles (P9 full après P11, P12.B live après
budget pub, P13 après domaine secondaire).

**3 nouveaux skills livrés (pattern markdown-only) :**

- [`.claude/skills/content-scheduler/`](../.claude/skills/content-scheduler/SKILL.md)
  — choisit l'heure et le jour optimaux pour publier un draft social
  (LinkedIn / Mastodon). Fenêtres canoniques par canal, espacement min
  entre 2 posts. Patch frontmatter draft → `status: validated` +
  `scheduled_for` ISO 8601 TZ Paris. Reddit retiré [D-022](DECISIONS.md#d-022--retrait-d%C3%A9finitif-de-reddit-du-p%C3%A9rim%C3%A8tre-argos-ops).
- [`.claude/skills/lead-enricher/`](../.claude/skills/lead-enricher/SKILL.md)
  — enrichit un lead BtoB depuis nom + domaine : 5 patterns email scorés,
  signaux ICP (persona Marc/Sarah/Thomas + taille boîte + secteur +
  funding + hiring + cloud migration), BANT 0-100 selon `ICP.md`.
  Heuristiques + sources publiques uniquement (pas d'Apollo / Hunter
  / Clearbit). Disqualifiers RGPD stricts (email perso → skip,
  concurrents → skip, < 10 pers → skip). Output dans
  `data/outbound/enriched/<lead>.md`.
- [`.claude/skills/outbound-personalizer/`](../.claude/skills/outbound-personalizer/SKILL.md)
  — génère **1 ligne** hyper-personnalisée (80-180 chars) à insérer en
  début de cold email. Règles strictes anti-fake-perso : source publique
  citée obligatoire, fait spécifique daté < 60 jours, zéro flatterie
  générique. Audit `claude-judge` (P14) avant insertion. Patch
  frontmatter de l'enriched.

**Status agents Python (P9/P12/P13)** :

| Agent | Skills disponibles | Connecteur Python | Statut |
|---|---|---|---|
| ContentBot (P9 full) | content-writer ✅ + content-scheduler ✅ | LinkedIn/Mastodon API (P11) | ⏳ attend P11 (Reddit retiré [D-022](DECISIONS.md#d-022--retrait-d%C3%A9finitif-de-reddit-du-p%C3%A9rim%C3%A8tre-argos-ops)) |
| AdBot live (P12.B) | ads-creative-writer ✅ + ads-optimizer ✅ | Google Ads / LinkedIn Marketing / Meta Marketing | ⏳ attend budget pub + credentials |
| OutboundBot (P13.A shadow) | lead-enricher ✅ + outbound-personalizer ✅ + zimbra-ops ✅ + claude-judge ✅ + **agent Python `OutboundBot` ✅** | zimbra-ops déjà en place — manque domaine secondaire ~10 €/an + `OUTBOUND_LIVE_MODE=true` pour P13.B (envoi réel) | 🔄 P13.A shadow done 2026-05-15 — drafts only |

### P17 — Conformité RGPD / AI Act / Bloctel ✅ done 2026-05-14

**Rédaction côté Argos Ops complète** (privacy + ai-disclosure faits en
P17-PREP le 2026-05-08). Cette session livre les pièces actionables
qui manquaient + finalise le statut.

**Code livré et tout vert** (ruff + format + mypy strict + **231 tests
passed** = 209 + 22 nouveaux) :

- [`argos_ops/compliance.py`](../argos_ops/compliance.py) — helper
  Python déterministe :
  - `is_human_response_requested(subject, body)` : détecte les
    expressions explicites de demande d'humain (FR + EN, ~20 variantes
    couvertes). Normalisation lowercase + retrait accents, regex avec
    word boundaries, fenêtre 500 premiers chars du body (ignore les
    signatures corporate type « Powered by HubSpot AI »)
  - **Sortie déterministe** — pas d'appel LLM, pas de dépendance
    externe, reproductible 100 %. Sert de contrat légal avec l'AI Act
    article 13 + notre engagement public `data/legal/ai-disclosure.md`
    § 5.2

- [`tests/test_compliance.py`](../tests/test_compliance.py) — 22 tests :
  - True cases : 7 variantes sujet + 4 variantes body + accents +
    ponctuation + body window
  - False cases : empty, unrelated, substrings dans mots (« inhumane »,
    « no Angular »), signature au-delà du window
  - Edge : subject only, body only, custom window

- Update [`.claude/skills/email-classifier/SKILL.md`](../.claude/skills/email-classifier/SKILL.md)
  — section « Override AI Act § 5.2 » avec liste des expressions
  déclencheuses + contrat de sortie (`category = "autre"`,
  `confidence = 1.0`, `suggested_response_skeleton = "PAS DE DRAFT IA"`)
- Update [`.claude/commands/check-emails.md`](../.claude/commands/check-emails.md)
  — step 2.a.0 : court-circuit AVANT classification IA via
  `is_human_response_requested()`. Garantit que l'humain qui exerce son
  droit AI Act voit son message quitter le pipeline IA immédiatement
- Update [`docs/COMPLIANCE.md`](../docs/COMPLIANCE.md) — section 7
  passée de « À compléter en P17 » à « Statut P17 (2026-05-14) » avec
  done / hors scope clair + engagement opérationnel (toute modif de
  sous-traitants / classification AI Act / phrases déclencheuses doit
  mentionner « P17 » dans le commit + bumper la date du markdown public)

**Done côté Argos Ops** :
- Page `/legal/privacy` rédigée (`data/legal/privacy.md`, 260 lignes,
  9 sections)
- Page `/legal/ai-disclosure` rédigée (`data/legal/ai-disclosure.md`,
  255 lignes, 8 sections + classification AI Act explicite)
- Sous-traitants (Anthropic, OVHcloud, Google Workspace, Stripe)
  documentés avec cadre RGPD (DPA + SCC 2021)
- Helper Python + tests + wire-up slash command
- Anti-fuite secrets (loguru filtre P4 + filtre Pydantic SecretStr)
  déjà actif depuis P4

**À faire hors Argos Ops (côté SecHunter / fondateur)** :
- Intégration frontend des 2 pages legal sur omnividens.fr
- Compléter placeholders dans privacy.md (forme juridique, SIREN, TVA,
  adresse siège, DPO externe)
- Confirmer / créer `security@omnividens.fr`
- Registre des traitements (modèle CNIL gratuit) à créer comme doc
  interne séparée
- Contrats type DPA pour clients enterprise (offre Custom ≥ 5 k€/mois)

### P12 — AdBot shadow mode 🔄 done 2026-05-14

Pattern aligné P9-DRAFT / P10-MVP : skills markdown + slash commands,
pas d'agent Python tant que les credentials Google Ads / LinkedIn
Marketing / Meta Marketing ne sont pas branchés. Sous D-017 et sans
budget pub, le plan § 12.1 prescrit explicitement le shadow mode comme
default — l'agent analyse + propose, l'humain applique manuellement.

**Livrables (aucun code Python — skills éditoriaux / analytiques purs)** :

- [`.claude/skills/ads-creative-writer/SKILL.md`](../.claude/skills/ads-creative-writer/SKILL.md)
  — génère 3 variantes A/B/C diversifiées (tech / bénéfice ops / risque
  légitime sans FUD) par draft. Respect strict contraintes plateforme :
  - Google Search RSA : 3-15 headlines ≤ 30 chars, 2-4 descriptions ≤ 90 chars
  - LinkedIn Sponsored : 1 headline ≤ 150 chars, 1 intro ≤ 600 chars
  - Meta : 1 primary text ≤ 125 chars, 1 headline ≤ 40 chars
  Audit `claude-judge` (P14) par variante avant écriture — variante
  `killed` rejetée + remplacée par une 4e.

- [`.claude/skills/ads-optimizer/SKILL.md`](../.claude/skills/ads-optimizer/SKILL.md)
  — lit CSV export Google Ads / LinkedIn Campaign Manager / Meta Ads
  Manager. Calcule CTR / CPC / CPA / conv rate vs S-1 (si CSV semaine
  précédente disponible). Produit 3-5 recommandations chiffrées
  (€/semaine d'impact) priorisées :
  1. PAUSE bleeding ≥ 2 sem
  2. DROP keyword (Google) ≥ 100 € spend / 0 conv / 2 sem
  3. TEST créa nouvelle (CTR < benchmark mais conv rate OK)
  4. SCALE +X % healthy ≥ 6 sem
  5. DIAGNOSTIC LP (CTR OK mais conv rate < 1 %)
  Évalue le breaker `ad_spend_runaway` (P15 § 15.1) et le trip
  proactivement si dépense > 1.5× budget cible / 24h, même en mode
  shadow (pour bloquer tout AdBot live mode futur).

- [`.claude/commands/draft-ad.md`](../.claude/commands/draft-ad.md)
  — slash command humain-in-the-loop. Demande explicitement
  `platform / objective / persona`. Refuse les paraphrases 3×, les
  superlatifs Google-bannis, les buzzwords corporate. Confirme avant
  d'attaquer Meta (canal bas priorité BtoB).

- [`.claude/commands/analyze-ads.md`](../.claude/commands/analyze-ads.md)
  — slash command humain-in-the-loop sur CSV. Demande CPA cible
  (défaut 80 € selon LTV Pro Max). Renomme automatiquement le CSV
  source vers `data/ads/campaigns/YYYY-MM-DD-<platform>.csv` après
  analyse pour servir de base de comparaison S+1.

- [`data/ads/`](../data/ads/) — pipeline complet documenté
  ([README](../data/ads/README.md)) :
  - `drafts/` — sortie `/draft-ad` (3 variantes par fichier)
  - `campaigns/` — CSV historiques pour comparaison S vs S-1
  - `recommendations/` — sortie `/analyze-ads` (3-5 actions chiffrées)

**Cycle de vie d'un draft Ad** : `draft → validated → live → (rejected)`
avec transitions manuelles côté fondateur. Quand P12.B live mode
arrivera (budget pub + credentials), un agent Python `ad_bot.py`
consommera la queue `validated`, soumettra à `claude-judge`, et postera
via API avec les hard caps du plan § 12.1 (pause auto si CPA > 2×
cible, +10 %/jour max sur budget, alerte si spend > 1.5× cible).

**Hors scope (reporté à P12.B live mode)** :

- Agent Python `argos_ops/agents/ad_bot.py` — nécessite credentials
  Google Ads (developer token + OAuth refresh token), LinkedIn Marketing
  API (déjà 2 apps créées en P1.E, en attente d'approbation Community
  Management), Meta Marketing API
- Wrappers API dans `argos_ops/integrations/{google_ads,linkedin_ads,meta_ads}.py`
- Cron Task Scheduler `argos-ops-ad-bot` (toutes les 4h en heures
  ouvrées selon plan § 12 livrables)

**Validation du critère plan § 12** (« 1 recommandation/jour Discord
avec rationale chiffré ») : reportée à la première campagne live du
fondateur. Pour l'instant les skills sont prêts, le pipeline est testé
côté workflow, il manque les vraies données pour calibrer.

### P13.A — OutboundBot shadow mode 🔄 done 2026-05-15

**Pivot stratégique** : décision fondateur du 2026-05-15 de ne pas
acheter tout de suite le domaine secondaire (~10 €/an). Plutôt que de
laisser P13 entièrement bloqué, on livre la **couche scaffold** de
l'agent (similaire aux pivots P9-DRAFT et P12 shadow) — drafts only,
zéro envoi tant que `OUTBOUND_LIVE_MODE=false` ET domaine secondaire
absent.

**Livrables (~600 lignes code + 250 lignes tests + docs)** :

- `argos_ops/outbound/` (Python pur, aucun LLM) :
  - `models.py` — `LeadInput`, `TouchStep` (DISCOVERY/VALUE/CASE/PROOF/BREAKUP),
    `Touch`, `SequenceState`
  - `templates.py` — `slugify()`, `compute_touch_dates()` (cadence
    D+0/D+3/D+7/D+14/D+30), `generate_opt_out_token()` HMAC-SHA256 16 chars,
    `verify_opt_out_token()` temps constant, `build_opt_out_url()`,
    `build_footer()` (RGPD + AI Act + opt-out)
  - `sequence.py` — `read_inbox_csv()` (parsing strict, refus colonnes
    inconnues + domain malformé), `scaffold_sequence_dir()` (idempotent,
    crée meta.yaml + 5 touch_N.md placeholders), `load_sequence_state()`,
    `is_sequence_scaffolded()`
- `argos_ops/agents/outbound_bot.py` — `OutboundBot(BaseAgent)` :
  - `command = "/run-outbound-bot"`, `breaker_name = "OutboundBot"`
  - Lit `data/outbound/inbox/leads.csv` si présent
  - Refuse si `OUTBOUND_UNSUBSCRIBE_SECRET` manquant (requis même en
    shadow pour pré-calculer les tokens HMAC)
  - Garde-fou volume : si > `OUTBOUND_DAILY_MAX` (défaut 30) nouveaux
    leads, trip breaker `outbound_volume_exceeded` AVANT scaffold
  - Notif Discord avec stats (`read`, `newly_scaffolded`, `already_scaffolded`,
    `failures`, liste des slugs créés)
- Slash commands :
  - `.claude/commands/run-outbound-bot.md` — wrapper cron-friendly
  - `.claude/commands/draft-outbound.md` — humain-in-the-loop pour
    drafter les bodies via `lead-enricher` + `outbound-personalizer` +
    `claude-judge` avant écriture
- Config :
  - `OUTBOUND_LIVE_MODE` (bool, défaut false)
  - `OUTBOUND_FROM_DOMAIN` (str, vide tant que pas acheté)
  - `OUTBOUND_UNSUBSCRIBE_SECRET` (SecretStr, obligatoire)
  - `OUTBOUND_DAILY_MAX` (int, défaut 30, warmup 5→10→20→30 sur 4 semaines)
- Breaker `outbound_volume_exceeded` ajouté à l'inventaire P15
- `data/outbound/` :
  - `README.md` workflow complet + format CSV + conformité RGPD/AI Act/Bloctel
  - `inbox/` (drop zone CSV) + `leads.example.csv`
  - `enriched/` (output skill lead-enricher)
  - `sequences/` (output OutboundBot + draft-outbound)
- Deps `pyyaml` ajouté en runtime (sérialisation `meta.yaml`) +
  `types-PyYAML` en dev

**Tests — 29 nouveaux, 260 au total** :
- slugify (4 cases : basique, accents, idempotent, troncature 50)
- cadence touch dates (2 : 5 dates calculées, constante 0/3/7/14/30)
- opt-out HMAC (9 : longueur 16 hex, déterministe, varie email/secret,
  email lowercase-normalized, verify accepts/rejects/wrong-secret, URL
  format)
- footer (1 cas couvrant les 5 éléments obligatoires)
- CSV parsing (7 : minimal, optional cols, commentés, domain invalide,
  colonne manquante, colonne inconnue, fichier inexistant)
- scaffold (6 : crée meta + 5 touches, idempotent, meta.yaml valide
  complet, is_sequence_scaffolded, load_sequence_state roundtrip,
  load raises if missing)

**Conformité dès la spec** :
- RGPD intérêt légitime BtoB (RGPD art. 6.1.f) — emails pro uniquement,
  perso à disqualifier côté `/draft-outbound`
- AI Act art. 50 — disclosure IA dans le footer via
  `EMAIL_SIGNATURE_AI_DISCLOSURE`
- Opt-out 1-clic HMAC-signé stateless — endpoint `/unsubscribe` à
  livrer en P13.B (FastAPI + table `unsubscribes`)
- Rétention 12 mois max — purge `data/outbound/sequences/` à câbler
  quand on aura du volume réel (P13.B+)
- Cap journalier hard via breaker — protection délivrabilité

**Hors scope P13.A** (volontaire — couvert par P13.B live mode) :
- Endpoint FastAPI `/unsubscribe` + table `unsubscribes` (migration)
- Connecteur SMTP envoi via Zimbra (zimbra-ops `send_email` déjà câblé,
  reste à brancher dans le pipeline outbound)
- Skill `outbound-drafter` (compose le body de chaque touche via KB
  + templates par step) — pour l'instant le slash `/draft-outbound`
  fait du humain-piloté
- Warmup automatique (rampe 5→10→20→30 sur 4 semaines) — manuel pour
  l'instant, le fondateur ajuste `OUTBOUND_DAILY_MAX` à la main
- Pull engagement (opens, clicks, replies via webhook ou IMAP scraping
  des bounces)
- Task Scheduler PowerShell `argos-ops-outbound-bot` — à créer quand
  P13.B live (sinon le run quotidien shadow n'apporte rien)

**Activation P13.B (futur)** quand domaine secondaire acheté :
1. Acheter `try-omnividens.com` ou équivalent (~10 €/an)
2. Configurer SPF / DKIM / DMARC stricts
3. Warm-up 4 semaines manuel (5 → 30 emails/jour)
4. Brancher skill `outbound-drafter` + connecteur SMTP outbound
5. Livrer endpoint `/unsubscribe` + table `unsubscribes`
6. Flip `OUTBOUND_LIVE_MODE=true` dans `.env`

### P19 — Maintenance et observabilité 🔄 P19.0 done 2026-05-14

**Premier livrable** : diagnostic CLI + module réutilisable. Hooks
Claude Code `PreToolUse`/`PostToolUse` du plan reportés (déjà couverts
fonctionnellement par `run_agent()` wrapper P15 qui check les breakers
+ logge `agent_runs` à chaque exécution).

**Code livré et tout vert** (ruff + format + mypy strict + **209 tests
passed** = 186 P0-P14 + 23 nouveaux) :

- [`argos_ops/health.py`](../argos_ops/health.py) — module réutilisable :
  - `HealthCheck` frozen dataclass (`name / status / detail / metric`)
  - `check_db_connectivity` — ping SELECT count sur kb_chunks
  - `check_kb_seeded` — red si 0 chunks, yellow si < `min_chunks` (50
    par défaut, critère P3), green sinon
  - `check_agent_freshness` — pour chaque agent attendu
    (DigestBuilder 26h / EmailBot 14.5h / FinanceBot 26h, cadences
    dérivées des Task Schedulers actifs CLAUDE.md) : red si run
    manquant ou trop vieux, yellow à 80 % du seuil (early warning),
    green sinon
  - `check_tripped_breakers` — yellow si breaker tripped, red si stale
    > 4 h (plan § 19.3 « 0 breaker actif > 4 h »)
  - `check_queued_escalations` — fenêtre 48 h sur `judge_verdict='queued'`
    (P14). Yellow > 10 items, red > 20 (le breaker
    `support_low_confidence` P15 trip à 50, on alerte avant)
  - `run_all_checks` — exécution **séquentielle** sur la même
    AsyncSession (SQLAlchemy interdit les ops concurrentes sur une
    session). Swallow individuel : un check qui crash devient red
    avec l'erreur en detail
  - `aggregate_health` — « worst status wins » + counts par statut

- [`scripts/health_check.py`](../scripts/health_check.py) — CLI :
  - Sortie humaine par défaut (overall + 5 checks avec status badges)
  - `--json` pour piping / dashboard
  - `--no-notify` pour skipper Discord (utile en debug local)
  - Notif Discord auto sur `DISCORD_WEBHOOK_OPS_LOGS` si overall != green
  - Exit code 0/1/2 (green/yellow/red) — compatible cron monitoring

- [`tests/test_health.py`](../tests/test_health.py) — 23 tests :
  - Immutabilité `HealthCheck`
  - Agrégation (vide, all-green, one-yellow, one-red dominates,
    detail formatting)
  - `check_kb_seeded` (3 cas : green / yellow / red)
  - `check_agent_freshness` (5 cas : tous frais, un stale, boundary
    80 %, jamais run, custom thresholds)
  - `check_tripped_breakers` (3 cas)
  - `check_queued_escalations` (3 cas + default threshold sanity)
  - `run_all_swallows_crash_per_check` — un check qui crash devient
    red, les autres tournent, agrégat reste cohérent

**Smoke test live (2026-05-14)** : `health_check.py --no-notify` a
détecté en condition réelle qu'`EmailBot` n'avait pas tourné depuis
115 h (cron probablement off depuis 5 jours côté fondateur). Le
diagnostic fait son job — la Task Scheduler est à investiguer côté
utilisateur.

**Hors scope (reporté à P19.1)** :

- Hooks Claude Code `PreToolUse` / `PostToolUse` — fonctionnalité déjà
  couverte par `run_agent()` (P15 breaker check + agent_runs log) +
  `check_runtime_state()` (P16.B disabled/paused/daily_limit). Sans
  doublons à introduire
- Endpoint dashboard `GET /health/detailed` — branchable trivialement
  sur `argos_ops.health.run_all_checks` quand le besoin se présente
- Cron Task Scheduler `argos-ops-health-check` (5h45 daily) — à créer
  côté fondateur via PowerShell scriptable (procédure type
  `digest-builder/SKILL.md`)

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
| ~~P11-PREP-A~~ | ~~Recréer Reddit App~~ | 🚫 **cancelled** ([D-022](DECISIONS.md#d-022--retrait-d%C3%A9finitif-de-reddit-du-p%C3%A9rim%C3%A8tre-argos-ops)) 2026-05-15 — Reddit retiré du périmètre Argos Ops | — |
| P11-PREP-B | Créer compte Mastodon infosec.exchange + token | ✅ done (compte `@argos_omnividens@infosec.exchange`, token validé via `scripts/smoke_mastodon.py` 2026-05-14) | TODO bio + bot flag |
| P17-PREP | Page `/legal/privacy` + `/legal/ai-disclosure` sur omnividens.fr | ⚠️ rédaction faite (data/legal/), intégration frontend SecHunter à faire par user | rédaction 2026-05-08 |
| P1.E-FOLLOWUP | Vérifier approbation Community Management API LinkedIn | ⬜ pending | 3-7j après 2026-05-07 |

---

## Métriques globales (à remplir à mesure)

- **Skills `argos-ops` créés :** 1 / 14 prévus (`digest-builder` en P4, voir P18)
- **Slash commands installés :** 1 (`/morning-digest` — partial, attend test live)
- **Agents en production :** 0 / 12 (DigestBuilder code livré, prod après finalisation P4)
- **Coût mensuel cumulé Argos Ops :** 0 € (cible : ≤ 1 €/mois en croisière)
