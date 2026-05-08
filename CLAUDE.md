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

- **Sessions terminées :** 3 / 19 (P0 + P1 + P2)
- **Phase en cours :** Sprint 0 — P3 à 60 % (bloc auto + P3-M1 + 3/6 fichiers KB livrés 2026-05-07)
- **Dernière partie done :** P2 — Bootstrap projet (2026-05-07)
- **Prochaine partie :** **reprise sur P3-M2** — il reste 3 fichiers KB à rédiger
  en mode interview (`argos_features.md`, `competitor_compare.md`, `faq.md`),
  puis **P3-M3** (seed KB + test similarité)
- **En attente review humaine :** [PR #4](https://github.com/Omnividens-argos/argos-ops/pull/4) (`feat/p3-crm-kb`, mergeable, CI ✅)
- **Flags ouverts à confirmer en début de prochaine session :** 3 calls par défaut
  marqués « à valider » dans `data/knowledge_base/pricing.md` :
  (A) `scans hors quota` add-on Free-only,
  (B) `IA fallback auto` Pro Max sans BYOK avec plafond serveur,
  (C) définitions de `Watch` + `Chaînes d'attaque`
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

> Vide pour l'instant. Premier slash command créé en P4 (`/morning-digest`).

---

## Skills locaux installés

- **`ui-ux-pro-max`** — design intelligence (50+ styles, 161 palettes, 57 font pairings,
  161 product types, 99 UX guidelines). Source : [nextlevelbuilder/ui-ux-pro-max-skill](https://github.com/nextlevelbuilder/ui-ux-pro-max-skill).
  À invoquer en P16 (Admin Control Panel) AVANT toute écriture de code frontend pour figer
  palette / typo / densité / layout. Nécessite Python 3.x pour le search script.

Inventaire métier prévu (P18) :
`digest-builder` · `gmail-ops` · `email-classifier` · `kb-rag` · `stripe-ops` ·
`chat-orchestrator` · `content-writer` · `content-scheduler` · `serp-analyzer` ·
`ads-optimizer` · `ads-creative-writer` · `lead-enricher` · `outbound-personalizer` ·
`claude-judge`

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
