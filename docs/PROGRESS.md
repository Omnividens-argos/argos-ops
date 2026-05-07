# Argos Ops — Progress

> Suivi de l'avancement des 19 parties du plan.
> Source : [`ARGOS_OPS_PLAN.md`](ARGOS_OPS_PLAN.md).
> À mettre à jour à chaque clôture de partie (règle « Clôture de partie » du
> [master prompt](MASTER_PROMPT.md)).

---

## Résumé d'avancement

- **Sessions terminées :** 3 / 19 (P0 + P1 + P2)
- **Phase en cours :** Sprint 0 — P3 en cours (bloc auto livré 2026-05-07, bloc manuel à faire)
- **Dernière partie done :** P2 — Bootstrap du dossier `argos-ops` (2026-05-07)
- **Prochaine partie :** P3 — Schéma CRM + Knowledge Base
- **Repo GitHub :** [Omnividens-argos/argos-ops](https://github.com/Omnividens-argos/argos-ops) (privé)

---

## Parties

| # | Titre | Sprint | Statut | Date |
|---|-------|--------|--------|------|
| 0 | Vision et décisions préalables | — | ✅ done | 2026-05-07 |
| 1 | Préparation technique et choix d'hébergement | — | ✅ done (partiel) | 2026-05-07 |
| 2 | Bootstrap du dossier `argos-ops` | Sprint 0 | ✅ done | 2026-05-07 |
| 3 | Schéma CRM + Knowledge Base | Sprint 0 | 🔄 in progress | bloc auto 2026-05-07 |
| 4 | `/morning-digest` (premier slash command) | Sprint 0 | ⬜ pending | — |
| 5 | EmailBot inbound | Sprint 1 | ⬜ pending | — |
| 6 | SupportBot Tier 1 (RAG sur KB) | Sprint 1 | ⬜ pending | — |
| 7 | FinanceBot (Stripe + relances) | Sprint 1 | ⬜ pending | — |
| 8 | Chatbot widget site (Gemini free) | Sprint 1 | ⬜ pending | — |
| 9 | ContentBot multi-canal | Sprint 2 | ⬜ pending | — |
| 10 | SEOBot stratégie + briefs | Sprint 2 | ⬜ pending | — |
| 11 | Connecteurs sociaux (LinkedIn / Mastodon / Reddit) | Sprint 2 | ⬜ pending | — |
| 12 | AdBot (pilotage Google/Meta/LinkedIn Ads) | Sprint 3 | ⬜ pending | — |
| 13 | OutboundBot (cold email volume modéré) | Sprint 3 | ⬜ pending | — |
| 14 | Agent-juge Tier 1 (supervision IA) | Sprint 4 | ⬜ pending | — |
| 15 | Circuit breakers et kill switches | Sprint 4 | ⬜ pending | — |
| 16 | Admin Control Panel (4 phases) | Sprints 1→4 | ⬜ pending | — |
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

À faire (bloc manuel) :
- Créer DB `argos_ops` + user dédié + extension `vector` sur cluster Postgres
  serveur (`204.168.171.71`, container `sechunter-postgres-1`).
- Appliquer `0001_init.sql`.
- Rédiger les 6 fichiers KB (`argos_features.md`, `pricing.md`, `faq.md`,
  `tone_of_voice.md`, `competitor_compare.md`, `ICP.md`) en mode interview pour
  capter la voix du fondateur.
- Lancer `uv run python scripts/seed_kb.py` → ≥ 50 chunks dans `kb_chunks`.
- Test similarité : « combien coûte Pro Max » doit retourner un chunk de
  `pricing.md` en top-1.

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
| P11-PREP-A | Recréer Reddit App (compte vieilli) | ⬜ pending | Avant P11 |
| P11-PREP-B | Créer compte Mastodon infosec.exchange + token | ⬜ pending | Avant P11 |
| P17-PREP | Créer vraie page `/legal/privacy` sur omnividens.fr | ⬜ pending | Avant P5 |
| P1.E-FOLLOWUP | Vérifier approbation Community Management API LinkedIn | ⬜ pending | 3-7j après 2026-05-07 |

---

## Métriques globales (à remplir à mesure)

- **Skills `argos-ops` créés :** 0 / 14 prévus (voir P18)
- **Slash commands installés :** 0
- **Agents en production :** 0 / 12
- **Coût mensuel cumulé Argos Ops :** 0 € (cible : ≤ 1 €/mois en croisière)
