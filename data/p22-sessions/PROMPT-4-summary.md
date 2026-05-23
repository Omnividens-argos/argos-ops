# Session 4 — Sprint 10 Finance avancé + Sprint 13 Documentation

**Date :** 2026-05-23
**Branche :** `feat/p22f-finance-docs-9-bots`
**Périmètre :** 9 nouveaux bots Python (6 Finance §2, 3 Documentation §11).

## Bots livrés

### Finance & Trésorerie (Sprint 10, 6 bots)

| Bot | Slash | Cron seul | Pattern |
|---|---|---|---|
| `InvoicePredictor` | `/run-invoice-forecast` | — | Forecast (drafte md) |
| `ExpenseAuditor` | `/run-expense-audit` | — | Watcher (CSV Qonto) |
| `TaxBot` | `/run-tax-prep` | — | Drafter (CA3 + IS) |
| `ReconcileBot` | `/run-reconcile` | — | Watcher (Stripe↔Qonto) |
| `BurnRateMonitor` | — | hebdo | Watcher (treasury YAML) |
| `VendorContractWatcher` | — | hebdo | Watcher (contracts YAML) |

### Documentation & Knowledge (Sprint 13, 3 bots)

| Bot | Slash | Pattern |
|---|---|---|
| `DocLinter` | `/run-doc-lint` | Watcher (md scan) |
| `DiagramGenerator` | `/gen-diagram <slug>` | Drafter (Mermaid) |
| `ADRWriter` | `/write-adr <slug>` | Drafter (MADR léger) |

## Architecture

Nouveau module **`argos_ops/finance/`** réutilisable :
- `tva.py` — TVA CA3 + IS PME 2024 (15 % / 25 %)
- `cash_flow.py` — forecast par fenêtre 30/60/90j
- `expense_csv.py` — parser Qonto (EN/FR), anomaly detector (outlier/dup/new_vendor)
- `reconcile.py` — matcher heuristique Stripe payouts ↔ Qonto credits

Pas de réécriture de `.claude/skills/stripe-ops/` (lecture seule, partagé avec Prompt 5).

## Convention watcher respectée

Tous les watchers (5/9) passent par `emit_alert_or_silence` du `_watcher_base` :
- `silence (vert)` quand RAS
- embed jaune / rouge selon sévérité
- pas de duplication de la logique anti-spam

Les 4 drafters (Invoice, Tax, Diagram, ADR) écrivent un fichier markdown et ne notifient pas Discord.

## Tests

**81 tests verts** dans 9 fichiers `tests/test_<bot>.py`. Run total `pytest` : **624 passed**.
Lint `ruff check` sur tous les fichiers livrés : **clean**.

## Annexe D

- 9 checkboxes cochées (§2 Finance × 6, §11 Documentation × 3).
- Compteur tête : `16 actifs → 25 actifs` (+9), `59 roadmap → 50 roadmap` (−9).
- Total cible 79 inchangé.

## Frontend catalog

`agentCatalog.ts` : 9 entrées passées de `roadmap` → `active` (slots Finance + Documentation). Aucune autre catégorie modifiée.

## Fichiers data créés

- `data/contracts/contracts.example.yaml`
- `data/finance/stripe_payouts.example.yaml`
- `data/finance/treasury_state.example.yaml`
- `data/expenses/.gitkeep`
- `docs/adr/.gitkeep`
- `docs/diagrams/.gitkeep`

## Commits prévus (LOCAUX, zéro push)

1. **`feat(p22f-finance): Sprint 10 — 6 bots Finance avancé`**
   InvoicePredictor + ExpenseAuditor + TaxBot + ReconcileBot + BurnRateMonitor + VendorContractWatcher
   + module `argos_ops/finance/` + 6 tests + 4 slash commands + 6 scripts CLI + 3 data examples
2. **`feat(p22f-docs): Sprint 13 — 3 bots Documentation`**
   DocLinter + DiagramGenerator + ADRWriter
   + 3 tests + 3 slash commands + 3 scripts CLI + 2 `.gitkeep`
   + Annexe D §2/§11 + agentCatalog.ts + compteur tête + ce résumé

## Points à valider en consolidation

- Compteur tête : si parallèle Prompt 5 a aussi bumpé, conflit à résoudre (mon delta = +9 actif / -9 roadmap).
- Pas de bot existant écrasé. Pas de modif `.claude/skills/stripe-ops/` ni `argos_ops/agents/finance_bot.py`.
- Tous mes scripts CLI suivent le pattern `run_<bot>.py` existant (windows event loop + dispose_engine).

Session 4 OK, prêt pour consolidation.
