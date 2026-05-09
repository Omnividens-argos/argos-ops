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
uv run python scripts/health_check.py  # diagnostic agents (P19+)
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
| `chat.omnividens.fr` | Endpoint chat widget FastAPI | P8 |
| `ops.omnividens.fr` | Admin Control Panel | P16 |
| `analytics.omnividens.fr` | Umami self-host | INFRA-02 |

Le Caddyfile en prod est dans le container `sechunter-caddy-1` sur le serveur
`204.168.171.71`. Variable `DOMAIN` configurée via docker-compose env.

---

## État d'avancement

> Source de vérité : [`docs/PROGRESS.md`](docs/PROGRESS.md).
> Le tableau ci-dessous est un mini-résumé, mis à jour à chaque clôture de partie.

- **Sessions terminées :** 5 / 19 (P0 + P1 + P2 + P3 + **P4 done** 2026-05-08 23:03 CET)
- **Phase en cours :** Sprint 1 — **P5 EmailBot inbound** (code livré + 67 tests verts 2026-05-09, en attente D-005 OVH + test live Zimbra)
- **Dernière partie done :** P4 — `/morning-digest` (test live `agent_runs id=2 status=success`, embed Discord OK)
- **Prochaine partie :** finaliser **P5** (D-005 + test live IMAP/SMTP, ~15 min manuel) puis **P6 SupportBot Tier 1** (RAG sur KB)
- **En attente review humaine :** PR P5 à créer (cette session) — wrapper
  `argos_ops/integrations/zimbra.py` + `EmailBot(BaseAgent)` + skills
  `zimbra-ops` / `email-classifier` + slash commands `/run-email-bot` /
  `/check-emails` + 27 nouveaux tests (67 total)
- **Tâche P4 cooldown (5 min) :** créer Task Scheduler Windows
  `argos-ops-morning-digest` (cf. `.claude/skills/digest-builder/SKILL.md`),
  schedule `0 8 * * *` Paris
- **Décisions P3-P5 actives :** D-009 à D-018 — voir [`docs/DECISIONS.md`](docs/DECISIONS.md).
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
  pour drafter les réponses aux emails inbound. Cf.
  [`.claude/commands/check-emails.md`](.claude/commands/check-emails.md)

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
- **`ui-ux-pro-max`** — design intelligence (50+ styles, 161 palettes, 57 font pairings,
  161 product types, 99 UX guidelines). Source : [nextlevelbuilder/ui-ux-pro-max-skill](https://github.com/nextlevelbuilder/ui-ux-pro-max-skill).
  À invoquer en P16 (Admin Control Panel) AVANT toute écriture de code frontend pour figer
  palette / typo / densité / layout. Nécessite Python 3.x pour le search script.

Inventaire métier prévu (P18) — restant à créer :
`kb-rag` · `stripe-ops` · `chat-orchestrator` · `content-writer` ·
`content-scheduler` · `serp-analyzer` · `ads-optimizer` · `ads-creative-writer` ·
`lead-enricher` · `outbound-personalizer` · `claude-judge`

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
