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

> Source de vérité : [`docs/PROGRESS.md`](docs/PROGRESS.md).
> Le tableau ci-dessous est un mini-résumé, mis à jour à chaque clôture de partie.

- **Sessions terminées :** 12 / 20 (P8 cancelled, P0-P7 + P15 + P16.A + P10-MVP + P16.B done, **refonte UX P16** 2026-05-12, **P20 Argos Memory** + **P21 Capabilities** spec ajoutées 2026-05-15)
- **Phase en cours :** Refonte UX du Admin Panel done — light/dark theme, 6 catégories d'agents avec slots roadmap, status pills multi-états, Overview enrichi (heatmap + sparklines + Today briefing), Runs groupé par jour + filtres multi, encart explicatif Breakers, 7 nouveaux agents au plan (Annexe D). **P20 Argos Memory** (D-020) + **P21 Paramétrage inter-agents** (D-021) spec rédigés.
- **Dernière partie done :** Refonte UX P16 — `ui-ux-pro-max` + `frontend-design` invoqués. Composants : `StatusPill`, `Sparkline`, `Heatmap`, `ThemeToggle`, `useTheme`, `agentCatalog`. CSS dual theme via custom properties.
- **Prochaine partie :** **P20.A Argos Memory foundation** (recommandé prioritaire — bus de communication entre agents, cf. [D-020](docs/DECISIONS.md#d-020--argos-memory--m%C3%A9moire-vivante-partag%C3%A9e-multi-agents-architecture-5-couches)) puis **P21.A Capabilities** (paramétrage inter-agents pull-based, cf. [D-021](docs/DECISIONS.md#d-021--param%C3%A9trage-inter-agents--capabilities-pull-based-default-allow-pour-read--deny-pour-write-back)). Sinon Sprint 2 — **P11-PREP** (Mastodon + Reddit + LinkedIn) puis **P11** (connecteurs sociaux) puis **P9** (ContentBot).
- **3 Task Scheduler actifs** : `argos-ops-morning-digest` (`0 8`) + `argos-ops-email-bot` (`*/15` 8h-22h) + `argos-ops-finance-bot` (`0 6`)
- **Décisions P3-P5 + P8 + P20 + P21 actives :** D-009 à D-021 — voir [`docs/DECISIONS.md`](docs/DECISIONS.md).
  **D-017 = révision architecturale majeure** : Argos Ops 100 % local-first
  via Claude Code Pro Max (agents) + `fastembed` / `paraphrase-multilingual-mpnet-base-v2`
  (embeddings). Aucune API LLM tierce. **D-018 = stack email** : OVH Zimbra
  IMAP/SMTP `ssl0.ovh.net:993/465`, boîte canonique `contact@omnividens.fr`.
- **Sécurité (2026-05-08) :** `argos_ops/logging.py` installe un filtre
  loguru anti-fuite sur les patterns secrets (webhooks Discord, sk- API,
  AIza, gh_, xox_, whsec_, AKIA). Auto-installé via `argos_ops/__init__.py`.
  Le filtre couvrira aussi automatiquement le mot de passe Zimbra (P5)
  via le redacting des `SecretStr` Pydantic.
- **Setup local requis :** container Docker `argos-postgres-local` doit tourner
  (`docker ps | grep argos-postgres-local`). Si arrêté, le redémarrer
  (`docker start argos-postgres-local`). Volume `argos_postgres_data` persistant.
  D-009 : DB serveur reportée à P4/P5.
- **En cours dans le working tree (non commité) :** install local du skill
  `.claude/skills/ui-ux-pro-max/` (référencé dans la section « Skills locaux
  installés » ci-dessous). À gérer dans une PR séparée si besoin.
- **Repo GitHub :** [Omnividens-argos/argos-ops](https://github.com/Omnividens-argos/argos-ops) (privé, branch protection active sur `main`)

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
- **`/draft-content`** (P9-DRAFT) — drafte un post social adapté à un
  canal (LinkedIn / Mastodon) depuis un topic + KB Argos. Reddit retiré
  [D-022](docs/DECISIONS.md#d-022--retrait-d%C3%A9finitif-de-reddit-du-p%C3%A9rim%C3%A8tre-argos-ops).
  Mode local-draft only — posting manuel jusqu'à P11. Humain-in-the-loop.
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
- **`content-writer`** (P9-DRAFT, 2026-05-14) — génère un post social
  adapté au canal (LinkedIn / Mastodon) depuis un topic + KB Argos (via
  `kb-rag`). Reddit retiré du périmètre [D-022](docs/DECISIONS.md#d-022--retrait-d%C3%A9finitif-de-reddit-du-p%C3%A9rim%C3%A8tre-argos-ops).
  Mode local-draft only — drafts rangés dans `data/content/drafts/` en
  attendant P11 (connecteurs sociaux). Réutilisé par `/draft-content` et
  futur ContentBot P9 full. Cf.
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
- [`docs/PROGRESS.md`](docs/PROGRESS.md) — état d'avancement
- [`docs/ARGOS_OPS_PLAN.md`](docs/ARGOS_OPS_PLAN.md) — plan stratégique 19 parties
- [`docs/MASTER_PROMPT.md`](docs/MASTER_PROMPT.md) — prompt de session pour Claude Code
