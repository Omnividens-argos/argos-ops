# Argos Ops — Instructions projet (CLAUDE.md)

> Lue par Claude Code à chaque session. **Concise et actionnable**. Le détail
> stratégique va dans [`docs/ARGOS_OPS_PLAN.md`](docs/ARGOS_OPS_PLAN.md) et les
> détails techniques dans `docs/`.

---

## Vision

Argos Ops est une **flotte d'agents IA** qui automatise l'acquisition, la
conversion, le support et l'admin de **Argos / SecHunter / Omnividens** (SaaS
pentest BtoB sur `omnividens.fr`). Objectif : libérer le fondateur du temps
opérationnel pour qu'il se concentre sur la stratégie et les vrais cas P0.

Contrainte non négociable : **0 € de SaaS récurrent** en plus de Claude Pro/Max.

---

## Workflow Git (obligatoire)

**Jamais de push direct sur `main`.** Tout passe par PR :

```bash
git checkout -b <type>/<description>      # feat/, fix/, refactor/, docs/, chore/
# ... modifications ...
git add -A && git commit -m "type: message"
git push -u origin <branche>
gh pr create --title "..." --body "..."
# attendre CI vert puis merger via GitHub
```

Branche protégée : merge impossible si CI échoue.

---

## Commandes courantes

```bash
uv sync                              # install deps
uv run pytest                        # tests
uv run pytest -v --tb=short          # tests verbeux
uv run ruff check .                  # lint
uv run ruff format .                 # format
uv run mypy argos_ops/               # type check strict
uv run python scripts/seed_kb.py     # rebuild KB embeddings (P3+)
uv run python scripts/health_check.py  # diagnostic agents + DB + breakers + queued (P19)
uv run python scripts/health_check.py --json --no-notify  # variantes (CI / debug)
```

---

## Conventions de code

- **Typage strict** (mypy strict, toutes les fonctions typées)
- **Async first** (httpx, FastAPI, asyncio)
- **BaseAgent** : tout agent hérite et implémente
  `async def run(self, config: AgentConfig) -> RunResult`
- **Logs** : `loguru` uniquement (jamais `print`, jamais `logging` stdlib)
- **Erreurs** : exceptions custom dans `argos_ops/exceptions.py`
- **Nommage** : fichiers `snake_case`, classes `PascalCase`,
  constantes `UPPER_SNAKE_CASE`
- **Sécurité** : aucun secret en dur, jamais de shell avec input non sanitisé,
  filtre loguru sur patterns clés API

---

## Sécurité des secrets

- `.env.local` (gitignored) — dev local
- `.env` (sur le serveur prod, gitignored) — prod
- `.env.example` (committed) — toutes les variables sans valeur
- Filtre loguru sur patterns : `sk-`, `AIza`, `gho_`, `WPL_AP1`, `xoxb-`,
  `whsec_`, `https://discord.com/api/webhooks/`
- `del key + gc.collect()` après usage de credentials sensibles

---

## Branding

- **Argos** = nom du produit
- **Omnividens** = nom de l'entreprise
- **Domaine** : `omnividens.fr` (pas `.com`)
- Toute URL publique : `https://omnividens.fr/...`

---

## Sous-domaines à brancher au fil des sprints

| Sous-domaine | Service | Partie |
|--------------|---------|--------|
| `ops.omnividens.fr` | Admin Control Panel | P16 |
| `analytics.omnividens.fr` | Umami self-host | INFRA-02 |

> _Note : `chat.omnividens.fr` initialement prévu pour la P8 chatbot widget
> est retiré du périmètre — cf. [D-019](docs/DECISIONS.md#d-019--abandon-d%C3%A9finitif-du-chatbot-widget-site-p8-cancelled)._

Le Caddyfile en prod est dans le container `sechunter-caddy-1` sur le serveur
`204.168.171.71`. Variable `DOMAIN` configurée via docker-compose env.

---

## État d'avancement

> **Source unique** : [`docs/ARGOS_OPS_PLAN.md` Annexe D](docs/ARGOS_OPS_PLAN.md#annexe-d--catalogue-cible--12-services--79-bots).
> Toute l'avancée bot par bot est cochée là (`[x] ✅` / `[~] 🟡` / `[ ] ⬜`).
> Ne PAS rajouter de section d'avancement ici — CLAUDE.md doit rester stable.

## Repo & contraintes runtime

- **Repo GitHub :** [Omnividens-argos/argos-ops](https://github.com/Omnividens-argos/argos-ops) (privé, branch protection sur `main`)
- **Décisions structurantes** : voir [`docs/DECISIONS.md`](docs/DECISIONS.md). Les plus impactantes :
  - **D-017** : Argos Ops 100 % local-first via Claude Code Pro Max + embeddings open-source (`fastembed` / `paraphrase-multilingual-mpnet-base-v2`). Aucune API LLM tierce.
  - **D-018** : stack email = OVH Zimbra IMAP/SMTP `ssl0.ovh.net:993/465`, boîte canonique `contact@omnividens.fr`.
- **Sécurité loguru** : `argos_ops/logging.py` installe un filtre anti-fuite sur les patterns secrets (webhooks Discord, `sk-`, `AIza`, `gh_`, `xox_`, `whsec_`, `AKIA`). Auto-installé via `argos_ops/__init__.py`.
- **Setup local requis** : container Docker `argos-postgres-local` doit tourner (`docker ps | grep argos-postgres-local`). Si arrêté, `docker start argos-postgres-local`.
- **Atelier libre embarqué** ([D-029](docs/DECISIONS.md)) : Claude Code piloté depuis le panel via CLI headless + WebSocket (`argos_ops/ops_dashboard/atelier.py`). OFF par défaut, **local-only**, flag `OPS_ATELIER_ENABLED=true`. RCE par conception — jamais exposé à distance. Moteur = CLI `claude` (abonnement Pro/Max, pas le SDK qui exige une API key). 2 modes : **lecture seule** + **pilotage flotte** (chef d'orchestre : lit la mémoire des bots et les lance via le serveur MCP `argos_ops/mcp/fleet_server.py` ; écriture scopée à `data/` pour les brouillons, le **code reste interdit** — Write/Edit hors `data/**` refusés). **Durcissement Axe 4 ([D-032](docs/DECISIONS.md))** : journal d'audit append-only redacté (`data/atelier_audit/`, gitignoré) sur chaque action irréversible ; rate-limit « 1 tour in-flight par session » (rejet `busy`, pas de file) ; MCP `run_bot` expose les IN/OUT redactés (sans `ref`) ; badge LIVE/SHADOW relu à chaud (poll + `refresh_settings` au moment d'agir).

## Convention watcher (P22.C)

Tout nouveau watcher hérite de `BaseAgent` et **DOIT** passer par
`argos_ops.agents._watcher_base.emit_alert_or_silence(report, embed_builder, agent_name)`
— ne pas dupliquer le pattern silence-si-vert dans `run()`. Le report
expose `should_alert: bool`, `alert_color: int`, `summary: str` (Protocol
`WatcherReport`). Helpers de formatage : `format_age`, `format_duration`,
`format_rate`, `color_title`.

## Convention cerveau (Axe 2 audit)

Un bot qui classifie/score peut consulter le **cerveau**
([`argos_ops/brain.py`](argos_ops/brain.py) — CLI `claude -p` one-shot, D-017,
flag `OPS_BRAIN_ENABLED` OFF par défaut) via `await think_json(prompt)`.
Règles non négociables (« le LLM propose, Python tranche ») : **fallback
heuristique** obligatoire si `answer.ok=False` (un bot ne crash jamais cerveau
OFF), **override humain** prioritaire, sortie **validée côté Python**
(enum/bornes/ids connus), contenu externe marqué **DONNÉE non fiable** dans le
prompt (anti-injection), et le cerveau ne **déclasse jamais** un signal
heuristique plus sévère. Référence : `EscalationRouter`
(`classify_with_brain` + `_resolve_priority`).

---

## Slash commands installés

- **`/morning-digest`** (P4) — digest quotidien Discord à 8h Paris.
  Cf. [`.claude/commands/morning-digest.md`](.claude/commands/morning-digest.md)
- **`/run-email-bot`** (P5) — pull IMAP toutes les 15 min, ingestion
  CRM, notif Discord. Pas de drafting ici (D-017). Cf.
  [`.claude/commands/run-email-bot.md`](.claude/commands/run-email-bot.md)
- **`/check-emails`** (P5) — slash command interactif humain-in-the-loop
  pour drafter les réponses aux emails inbound. Invoque `kb-rag` (P6).
  Cf. [`.claude/commands/check-emails.md`](.claude/commands/check-emails.md)
- **`/run-support-tier1`** (P6) — répond à une question support Tier 1 via
  RAG sur KB (anti-hallucination strict). Cf.
  [`.claude/commands/run-support-tier1.md`](.claude/commands/run-support-tier1.md)
- **`/daily-finance-sync`** (P7) — sync Stripe quotidienne (subs + factures +
  MRR/ARR + dunning J+3/J+7/J+15 + alerte Discord baisse MRR). Cf.
  [`.claude/commands/daily-finance-sync.md`](.claude/commands/daily-finance-sync.md)
- **`/reset-breaker`** (P15) — reset manuel d'un circuit breaker. Sans
  argument, liste les breakers tripped. Cf.
  [`.claude/commands/reset-breaker.md`](.claude/commands/reset-breaker.md)
- **`/generate-seo-brief`** (P10-MVP) — drafte un brief blog SEO
  structuré (titre, outline H2/H3, sources, meta, internal links) à
  partir d'un keyword + KB Argos. Humain-in-the-loop. Cf.
  [`.claude/commands/generate-seo-brief.md`](.claude/commands/generate-seo-brief.md)
- **`/draft-linkedin`** · **`/draft-mastodon`** · **`/draft-bluesky`**
  (Sprint contenu, 2026-06-01) — slashs dédiés par canal, un writer par
  réseau (`linkedin-writer` 1300-2000 chars / `mastodon-writer` 300-500
  chars infosec.exchange / `bluesky-writer` ≤300 graphemes AT Protocol).
  Humain-in-the-loop, charge KB + audit `claude-judge`, mode local-draft.
  Cf. [`.claude/commands/`](.claude/commands/).
- **`/draft-content`** (déprécié → aiguillage) — route vers le slash dédié
  selon le canal. Reddit retiré
  [D-022](docs/DECISIONS.md#d-022--retrait-d%C3%A9finitif-de-reddit-du-p%C3%A9rim%C3%A8tre-argos-ops).
  Cf. [`.claude/commands/draft-content.md`](.claude/commands/draft-content.md)
- **`/draft-ad`** (P12 shadow) — drafte 3 variantes d'annonce Ads
  (Google Search RSA / LinkedIn Sponsored / Meta) avec audit `claude-judge`
  par variante. Mode shadow uniquement — pas de publication API tant que
  P12.B live mode n'est pas activé. Humain-in-the-loop. Cf.
  [`.claude/commands/draft-ad.md`](.claude/commands/draft-ad.md)
- **`/analyze-ads`** (P12 shadow) — analyse un CSV export Ads et produit
  3-5 recommandations chiffrées (€/semaine) dans `data/ads/recommendations/`.
  Évalue le breaker `ad_spend_runaway`. Aucune action plateforme. Cf.
  [`.claude/commands/analyze-ads.md`](.claude/commands/analyze-ads.md)
- **`/run-outbound-bot`** (P13.A shadow) — lance `OutboundBot` qui
  scaffold les séquences cold email 5-touches (D+0/D+3/D+7/D+14/D+30)
  depuis `data/outbound/inbox/leads.csv`. Idempotent, aucun envoi
  tant que `OUTBOUND_LIVE_MODE=false`. Cf.
  [`.claude/commands/run-outbound-bot.md`](.claude/commands/run-outbound-bot.md)
- **`/draft-outbound <slug>`** (P13.A shadow) — humain-in-the-loop pour
  remplir le body de chaque touche via `lead-enricher` +
  `outbound-personalizer` + `claude-judge`. Garde-fous email perso
  disqualifié, BANT < 40 refusé, footer opt-out HMAC obligatoire. Cf.
  [`.claude/commands/draft-outbound.md`](.claude/commands/draft-outbound.md)
- **`/run-fleet-watchdog`** (Axe 3.2, [D-031](docs/DECISIONS.md)) — lance
  `FleetWatchdog`, **SRE unifié** qui fusionne les 4 anciens watchers
  `agent_runs` (BotHealthBot + BotPerfAnalyzer + ErrorTriageBot +
  LogAnomalyDetector) : 1 passe DB, 4 sections (santé/freshness · perf
  P50/P95 · triage erreurs par signature · anomalie de volume), **1 embed
  multi-sections** sur `DISCORD_WEBHOOK_OPS_LOGS`, silence si les 4 sections
  sont vertes (couleur globale = la plus sévère). Task Scheduler
  `argos-ops-fleet-watchdog` toutes les 6h. Remplace `/run-bot-health`,
  `/run-bot-perf`, `/run-error-triage`, `/run-log-anomalies`. Logique pure
  des 4 sections dans `argos_ops/agents/_watchdog/`. Cf.
  [`.claude/commands/run-fleet-watchdog.md`](.claude/commands/run-fleet-watchdog.md)
- **`/run-config-drift`** (P22.C) — `BotConfigManager`, diff `agent_config` DB vs `data/agent_config/baseline.yaml`.
- **`/run-uptime`** (P22.C) — `UptimeMonitor`, ping endpoints `data/uptime/endpoints.yaml`.
- **`/run-secret-audit`** (P22.C) — `SecretRotator`, alerte secrets > 90j depuis `data/secrets/rotation_log.yaml` (fichier en exception `.gitignore`, jamais de valeurs).
- **`/run-dep-audit`** (P22.C) — `DependencyAuditor`, scan deps `uv export` + check CVE OSV.dev (alerte HIGH/CRITICAL).
- _3 watchers P22.C sans slash (cron pur) :_ `KillSwitchOperator`, `SSLExpirer`, `BackupVerifier`.
- **`/orchestrate`** (P22.B) — lance `OrchestratorBot`, chef de fleet.
  Décide quels bots doivent tourner maintenant à partir de la cadence
  cron canonique + config runtime + breakers + daily_limit. Mode
  dry-run par défaut (logue le plan, ne lance rien), `--live` pour
  exécuter avec sémaphore `max_concurrent=2`. Hooks
  `_consume_memory()` / `_consume_capabilities()` placeholders
  (branchés P20.A / P21). Cf.
  [`.claude/commands/orchestrate.md`](.claude/commands/orchestrate.md)
- **`/run-memory-curator`** (P20, [D-028](docs/DECISIONS.md#d-028--m%C3%A9moire-de-flotte-100--fichiers-locale-remplace-le-design-db-de-la-partie-20)) —
  lance `MemoryCurator`, concierge de la mémoire de flotte
  (`data/fleet_memory/`). Archive le périmé (TTL) + le stale, purge le très
  vieux déjà archivé (hard delete), protège les faits `pinned`. Seul bot
  autorisé à supprimer un fait. Silence Discord si rien à nettoyer. Cf.
  [`.claude/commands/run-memory-curator.md`](.claude/commands/run-memory-curator.md)

---

## Skills locaux installés

- **`digest-builder`** (P4) — KPIs J-1 → embed Discord. Cf.
  [`.claude/skills/digest-builder/`](.claude/skills/digest-builder/)
- **`zimbra-ops`** (P5, D-018) — lire/drafter/envoyer/marquer emails sur
  OVH Zimbra IMAP/SMTP. Réutilisé par EmailBot, OutboundBot (P13),
  FinanceBot (P7). Cf. [`.claude/skills/zimbra-ops/`](.claude/skills/zimbra-ops/)
- **`email-classifier`** (P5) — Claude inline, classifie en
  `lead_chaud / question_tech / sav / spam / partenariat / recrutement /
  presse / autre`. Cf. [`.claude/skills/email-classifier/`](.claude/skills/email-classifier/)
- **`kb-rag`** (P6) — recherche similarité fastembed local + pgvector cosine
  sur la KB Argos. Réutilisé par `/check-emails`, `/run-support-tier1`. (Sera
  aussi consommé par ContentBot P9 et OutboundBot P13.) Cf.
  [`.claude/skills/kb-rag/`](.claude/skills/kb-rag/)
- **`stripe-ops`** (P7) — wrapper Stripe + calcul MRR/ARR + classification
  dunning J+3/J+7/J+15 + envoi relances (3 templates dégradés). Réutilisé
  par `/daily-finance-sync`. Cf. [`.claude/skills/stripe-ops/`](.claude/skills/stripe-ops/)
- **`seo-brief-writer`** (P10-MVP) — génère un brief blog SEO structuré
  depuis un keyword + KB Argos (via `kb-rag`). Pas de SERP scraping
  (option A 2026-05-12). Réutilisé par `/generate-seo-brief` et futur
  ContentBot P9. Cf. [`.claude/skills/seo-brief-writer/`](.claude/skills/seo-brief-writer/)
- **`linkedin-writer`** · **`mastodon-writer`** · **`bluesky-writer`**
  (Sprint contenu, 2026-06-01) — skills éditoriaux **dédiés par canal**
  (split de l'ancien `content-writer`). Chacun charge la KB (`kb-rag`),
  audite via `claude-judge` avant écriture, et range le draft dans
  `data/content/drafts/`. Connecteurs Sprint A
  ([`argos_ops/social/`](argos_ops/social/)) : LinkedIn / Mastodon live,
  Bluesky AT Protocol (gratuit). Anti-FUD strict. Cf.
  [`.claude/skills/`](.claude/skills/).
- **`content-writer`** (déprécié 2026-06-01) — ancien skill multi-canal,
  scindé en `linkedin-writer` / `mastodon-writer` / `bluesky-writer`.
  Conservé en référence historique uniquement, ne plus invoquer. Cf.
  [`.claude/skills/content-writer/`](.claude/skills/content-writer/)
- **`claude-judge`** (P14, 2026-05-14) — agent-juge Tier 1. Note un
  draft sur 3 axes (factual / tone / legal, 0-100) et retourne un JSON
  parseable par [`argos_ops/judge.py`](argos_ops/judge.py). Sous D-017
  c'est Claude Code lui-même qui joue ce rôle, invoqué dans
  `/check-emails`, `/draft-content`, `/generate-seo-brief` (et futur
  `/draft-outbound` P13) AVANT validation humaine. Verdict canonique
  (auto_send / queued / killed) tranché côté Python via
  `apply_thresholds()` selon `docs/ESCALATION_RULES.md`. 5 fixtures
  starter dans `data/judge/fixtures/`. Cf.
  [`.claude/skills/claude-judge/`](.claude/skills/claude-judge/)
- **`ui-ux-pro-max`** — design intelligence (50+ styles, 161 palettes, 57 font pairings,
  161 product types, 99 UX guidelines). Source : [nextlevelbuilder/ui-ux-pro-max-skill](https://github.com/nextlevelbuilder/ui-ux-pro-max-skill).
  À invoquer en P16 (Admin Control Panel) AVANT toute écriture de code frontend pour figer
  palette / typo / densité / layout. Nécessite Python 3.x pour le search script.

- **`ads-creative-writer`** (P12 shadow, 2026-05-14) — génère 3
  variantes d'annonce Ads (Google Search RSA / LinkedIn Sponsored /
  Meta) à partir d'un objectif + persona ICP + KB Argos. Respecte
  contraintes plateforme (longueurs, headlines count). Audit
  `claude-judge` par variante avant écriture. Réutilisé par `/draft-ad`
  et futur AdBot Python P12.B. Cf.
  [`.claude/skills/ads-creative-writer/`](.claude/skills/ads-creative-writer/)
- **`ads-optimizer`** (P12 shadow, 2026-05-14) — lit un CSV export
  Google Ads / LinkedIn Campaign Manager / Meta Ads Manager, calcule
  CTR/CPC/CPA/conv rate vs S-1, propose 3-5 actions chiffrées (€/semaine
  d'impact). Évalue le breaker `ad_spend_runaway` (P15). Réutilisé par
  `/analyze-ads` et futur AdBot Python P12.B. Cf.
  [`.claude/skills/ads-optimizer/`](.claude/skills/ads-optimizer/)
- **`content-scheduler`** (P18, 2026-05-14) — choisit l'heure et le jour
  optimaux pour publier un draft social (LinkedIn / Mastodon). Reddit
  retiré [D-022](docs/DECISIONS.md#d-022--retrait-d%C3%A9finitif-de-reddit-du-p%C3%A9rim%C3%A8tre-argos-ops).
  Respecte les fenêtres d'engagement par canal et un espacement minimal
  entre 2 posts d'un canal. Patch le frontmatter du draft (`status:
  validated` + `scheduled_for` + `scheduling_rationale`). Cf.
  [`.claude/skills/content-scheduler/`](.claude/skills/content-scheduler/)
- **`lead-enricher`** (P18, 2026-05-14) — enrichit un lead BtoB depuis
  un input minimal (nom + domaine). Devine l'email pro (5 patterns
  scorés), titre, signaux ICP (Marc/Sarah/Thomas), BANT 0-100.
  Heuristiques + sources publiques uniquement, aucune API tierce
  (Apollo/Hunter en option P13.B si budget). Disqualifiers RGPD
  stricts (email perso → skip). Output dans
  `data/outbound/enriched/<lead>.md`. Cf.
  [`.claude/skills/lead-enricher/`](.claude/skills/lead-enricher/)
- **`outbound-personalizer`** (P18, 2026-05-14) — génère **1 ligne**
  hyper-personnalisée (80-180 chars) à insérer en début de cold email
  Argos, à partir d'une fiche enriched. Règles strictes anti-fake-perso :
  source publique citée obligatoire, fait spécifique daté < 60 jours,
  zéro flatterie générique. Audit `claude-judge` (P14) avant insertion.
  Patch le frontmatter de l'enriched. Cf.
  [`.claude/skills/outbound-personalizer/`](.claude/skills/outbound-personalizer/)
- **`compliance`** (P17, 2026-05-14) — pas un skill markdown : helper
  Python [`argos_ops/compliance.py`](argos_ops/compliance.py) qui
  encode les checks déterministes RGPD / AI Act qu'on ne veut PAS
  déléguer à un LLM. Premier check livré :
  `is_human_response_requested()` — détecte les demandes explicites
  de réponse humaine (AI Act § 5.2), court-circuite la classification
  IA dans `/check-emails`. 22 tests.

**Inventaire P18 complet** — tous les skills planifiés du plan §18 sont
livrés (sauf `serp-analyzer` reporté en P10.1 — option B 2026-05-12).
Les agents Python correspondants (`ContentBot` P9 full, `OutboundBot` P13,
`AdBot` P12.B live mode) restent à câbler avec leurs connecteurs API
respectifs quand les credentials / budgets associés seront disponibles.

_(`chat-orchestrator` retiré de l'inventaire par [D-019](docs/DECISIONS.md#d-019--abandon-d%C3%A9finitif-du-chatbot-widget-site-p8-cancelled).)_

---

## Pour aller plus loin

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — vue technique globale
- [`docs/AGENTS_PLAYBOOK.md`](docs/AGENTS_PLAYBOOK.md) — détail des 12 agents
- [`docs/ESCALATION_RULES.md`](docs/ESCALATION_RULES.md) — règles Tier 0-4
- [`docs/COMPLIANCE.md`](docs/COMPLIANCE.md) — RGPD / AI Act / Bloctel
- [`docs/DECISIONS.md`](docs/DECISIONS.md) — journal des décisions structurantes
- [`docs/ARGOS_OPS_PLAN.md`](docs/ARGOS_OPS_PLAN.md) — plan stratégique + **Annexe D = source unique avancement bots**
- [`docs/MASTER_PROMPT.md`](docs/MASTER_PROMPT.md) — prompt de session pour Claude Code
