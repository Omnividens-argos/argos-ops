# Argos Ops — Instructions projet (CLAUDE.md)

> Lue par Claude Code à chaque session. **Concise et actionnable**. Le détail
> stratégique va dans `../the good guy/docs/ARGOS_OPS_PLAN.md` et les détails
> techniques dans `docs/`.

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

- **Sessions terminées :** 2 / 19 (P0 + P1)
- **Phase en cours :** Sprint 0 (Bootstrap)
- **Dernière partie done :** P1 (2026-05-07)
- **Prochaine partie :** P2 (Bootstrap projet — en cours)

---

## Slash commands installés

> Vide pour l'instant. Premier slash command créé en P4 (`/morning-digest`).

---

## Skills locaux installés

> Vide pour l'instant. Premier skill créé en P4 (`digest-builder`).

Inventaire prévu (P18) :
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
- [`../the good guy/docs/ARGOS_OPS_PLAN.md`](../the%20good%20guy/docs/ARGOS_OPS_PLAN.md) — plan stratégique 19 parties
