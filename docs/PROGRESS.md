# Argos Ops — Progress

> Suivi de l'avancement des 19 parties du plan.
> Source : [`ARGOS_OPS_PLAN.md`](ARGOS_OPS_PLAN.md).
> À mettre à jour à chaque clôture de partie (règle « Clôture de partie » du
> [master prompt](MASTER_PROMPT.md)).

---

## Résumé d'avancement

- **Sessions terminées :** 3 / 19 (P0 + P1 + P2)
- **Phase en cours :** Sprint 0 — P3 à 90 % (bloc auto + P3-M1 + **P3-M2 complet** livré 2026-05-08, reste P3-M3 seed)
- **Dernière partie done :** P2 — Bootstrap du dossier `argos-ops` (2026-05-07)
- **Prochaine partie :** **P3-M3** — `uv run python scripts/seed_kb.py` → ≥ 50 chunks dans `kb_chunks` + test similarité « combien coûte Pro Max » → top-1 chunk de `pricing.md`
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

P3-M3 — Seed + validation (⬜ à faire, auto) :
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
